#!/usr/bin/env python3
from argparse import ArgumentParser, FileType
import csv
import itertools
import math
import random
import struct

import wave

SAMPWIDTH = 2 # 16-bit audio

CHARS = {
    'a': '.-',
    'b': '-...',
    'c': '-.-.',
    'd': '-..',
    'e': '.',
    'f': '..-.',
    'g': '--.',
    'h': '....',
    'i': '..',
    'j': '.---',
    'k': '-.-',
    'l': '.-..',
    'm': '--',
    'n': '-.',
    'o': '---',
    'p': '.--.',
    'q': '--.-',
    'r': '.-.',
    's': '...',
    't': '-',
    'u': '..-',
    'v': '...-',
    'w': '.--',
    'x': '-..-',
    'y': '-.--',
    'z': '--..',
    ' ': ' ',
    ',': '--..--',
    '?': '..--..',
    '.': '.-.-.-',
    }

def normalise_char(char):
    if char.isspace():
        return ' '
    return char.lower()

def normalise_special_characters(char):
    from unidecode import unidecode
    return unidecode(char)

def char_to_cw(char, normalise):
    if normalise:
        char = normalise_special_characters(char)
    char = normalise_char(char)

    return CHARS[char]

def cycle_n(xs, n):
    length = len(xs)
    periods = math.floor(n / length)
    rest = n - periods * length
    return periods * xs + xs[:rest]

def sine_wave(frequency, duration, frame_rate=44100, amplitude=0.5):
    period = int(frame_rate / frequency)
    amp = min(max(amplitude, 0.0), 1.0)
    lookup_table = [amplitude *
            math.sin(2.0 * math.pi * frequency * (i%period) / frame_rate)
            for i in range(period)]

    return cycle_n(lookup_table, int(duration * frame_rate / 1000))

def noise_generator(kind, duration, frame_rate=44100, amplitude=0.5):
    from acoustics.generator import noise
    samples = noise(frame_rate, kind)
    samples = [s / 5 * amplitude for s in samples]

    return cycle_n(samples, int(duration * frame_rate / 1000))

def mix(*signals):
    return map(sum, zip(*signals))

class CWGenerator:
    def __init__(self,
            wpm,
            min_wpm,
            max_wpm,
            length_standard_deviation=0.0,
            length_drift=0.0,
            normalise_special_characters=False):
        self.wpm = wpm
        self.min_wpm = min_wpm
        self.max_wpm = max_wpm
        self.length_standard_deviation = length_standard_deviation
        self.length_drift = length_drift
        self.normalise_special_characters = normalise_special_characters

    def dot_length(self):
        length = math.floor(1200 / self.wpm)
        dev = length * self.length_standard_deviation
        length = max(0, min(max(length - dev, random.gauss(length, dev)), length + dev))
        return length

    def dash_length(self):
        return 3 * self.dot_length()

    def produce_char(self, char):
        elems = char_to_cw(char, self.normalise_special_characters)
        i = 0
        for elem in elems:
            if elem == '.':
                yield (True, self.dot_length())
            elif elem == '-':
                yield (True, self.dash_length())
            elif elem == ' ':
                yield (False, self.dot_length() * 4)
            i += 1
            if i < len(elems):
                yield (False, self.dot_length())
        yield (False, self.dash_length())

    def drift(self):
        drift = random.gauss(1.0, self.length_drift)
        drift = min(max(drift, 1 - self.length_drift), 1 + self.length_drift)
        self.wpm *= drift
        if self.min_wpm is not None: self.wpm = max(self.min_wpm, self.wpm)
        if self.max_wpm is not None: self.wpm = min(self.max_wpm, self.wpm)

    def produce(self, string):
        for char in string:
            yield from self.produce_char(char)
            self.drift()

def generate_wav(stream, frame_rate=44100, frequency=600,
        noise_kind=None, noise_level=0.0):
    max_amp = int(2 ** (8 * SAMPWIDTH - 1)) - 1

    audio = []
    length = 0
    for on, duration in stream:
        audio.append(sine_wave(
                frequency=frequency,
                duration=duration,
                frame_rate=frame_rate,
                amplitude=0.5 * max_amp if on else 0.0))
        length += duration
    audio = [a for parts in audio for a in parts]
    if noise_level > 0.0:
        noise = noise_generator(
                noise_kind,
                length,
                frame_rate,
                noise_level * max_amp)
        audio = mix(audio, noise)
    audio = list(map(int, audio))
    frames = struct.pack('{0:d}h'.format(len(audio)), *audio)

    return frames

def main():
    parser = ArgumentParser(
            description='Generate CW (morse code) audio files from text')

    g_files = parser.add_argument_group('Input/Output')
    g_files.add_argument('--input', '-i', type=FileType('r'),
            help='Read text from this file', required=True)
    g_files.add_argument('--wave', '-w', type=FileType('wb'),
            help='Write WAVE output to this file')
    g_files.add_argument('--frame-rate', type=int, default=22050,
            help='Frame rate in Hz (default: 22050)')
    g_files.add_argument('--csv', type=FileType('w'),
            help='Write CSV output to this file')
    g_files.add_argument('--quiet', '-q', action='store_true',
            help='Be more quiet')
    g_files.add_argument('--play', '-p', action='store_true',
            help='Playback')

    g_gen = parser.add_argument_group('CW Generation')
    g_gen.add_argument('--normalise-special-characters', '-c', action='store_true',
            help='Normalise special characters, like á to a')
    g_gen.add_argument('--frequency', '-f', type=int, default=600,
            help='Tone frequency in Hz (default: 600)')
    g_gen.add_argument('--wpm', '-s', type=int, default=12,
            help='Initial speed in WPM (default: 12)')
    g_gen.add_argument('--max-wpm', type=int, default=None,
            help='Maximum speed in WPM (default: none)')
    g_gen.add_argument('--min-wpm', type=int, default=None,
            help='Minimum speed in WPM (default: none)')
    g_gen.add_argument('--length-standard-deviation', '-d', type=float, default=0.0,
            help='Standard deviation from dotlength, '
                'relative to the dot length (default: 0.0; sensible: < 0.2)')
    g_gen.add_argument('--length-drift', '-D', type=float, default=0.0,
            help='Speed drift (default: 0.0; suggested: 0.02)')

    g_noise = parser.add_argument_group('Noise Generation')
    g_noise.add_argument('--noise-kind', '-N', type=str, default='pink',
            help='Noise kind (default: pink; other values: white, blue, brown, violet)')
    g_noise.add_argument('--noise-level', '-n', type=float, default=0.0,
            help='Add noise with this amplitude (0 <= a <= 1; default: 0)')

    args = parser.parse_args()

    if not args.quiet:
        print('cwgen.py  Copyright (C) 2018  Camil Staps')
        print('This program comes with ABSOLUTELY NO WARRANTY.')
        print('This is free software, and you are welcome to redistribute it under certain conditions.')
        print('See the LICENSE file for details.')

    gen = CWGenerator(
            wpm=args.wpm,
            min_wpm=args.min_wpm,
            max_wpm=args.max_wpm,
            length_standard_deviation=args.length_standard_deviation,
            length_drift=args.length_drift,
            normalise_special_characters=args.normalise_special_characters)
    stream = list(gen.produce(args.input.read()))

    if args.csv is not None:
        wr = csv.writer(args.csv)
        wr.writerow(['On','Duration'])
        for on, duration in stream:
            wr.writerow([on, int(duration)])

    if args.wave is not None or args.play:
        frames = generate_wav(stream, args.frame_rate, args.frequency,
                args.noise_kind, args.noise_level)

        if args.wave is not None:
            wav = wave.open(args.wave)
            wav.setnchannels(1)
            wav.setsampwidth(SAMPWIDTH)
            wav.setframerate(args.frame_rate)
            wav.writeframes(frames)
        if args.play:
            import pyaudio
            player = pyaudio.PyAudio()
            player = player.open(
                    format=player.get_format_from_width(SAMPWIDTH),
                    channels=1,
                    rate=args.frame_rate,
                    output=True)
            try:
                block_size = int(args.frame_rate / 4)
                while len(frames) > 0:
                    data = frames[:block_size]
                    frames = frames[block_size:]
                    player.write(data)
            except KeyboardInterrupt:
                pass

if __name__ == '__main__':
    main()
