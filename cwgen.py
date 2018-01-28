#!/usr/bin/env python3
from argparse import ArgumentParser, FileType
import itertools
import math
import random
import struct

from acoustics.generator import noise
import wave

FRAMERATE = 44100
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

def char_to_cw(char, normalise):
    if normalise:
        char = normalise_special_characters(char)
    char = normalise_char(char)

    return CHARS[char]

# After https://zach.se/generate-audio-with-python/
def sine_wave(frequency, framerate=44100, amplitude=0.5):
    period = int(framerate / frequency)
    amp = min(max(amplitude, 0.0), 1.0)
    lookup_table = [amplitude *
            math.sin(2.0 * math.pi * frequency * (i%period) / framerate)
            for i in range(period)]
    return (lookup_table[i%period] for i in itertools.count(0))

# After https://zach.se/generate-audio-with-python/
def white_noise(amplitude=0.5):
    return (float(amplitude) * random.uniform(-1, 1) for i in itertools.count(0))

def noise_generator(kind, amplitude):
    samples = noise(FRAMERATE, kind)
    samples = [s / 5 * amplitude for s in samples]
    return itertools.cycle(samples)

def mix(*signals):
    return map(sum, zip(*signals))

class CWGenerator:
    def __init__(self,
            wpm,
            length_standard_deviation=0.0,
            length_drift=0.0,
            normalise_special_characters=False):
        self.wpm = wpm
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

    def produce(self, string):
        for char in string:
            yield from self.produce_char(char)
            drift = random.gauss(1.0, self.length_drift)
            drift = min(max(drift, 1 - self.length_drift), 1 + self.length_drift)
            self.wpm *= drift

def main():
    parser = ArgumentParser(
            description='Generate CW (morse code) audio files from text')

    g_files = parser.add_argument_group('Input/Output')
    g_files.add_argument('--input', type=FileType('r'),
            help='Read text from this file', required=True)
    g_files.add_argument('--wave', type=FileType('wb'),
            help='Write WAVE output to this file')
    g_files.add_argument('--quiet', '-q', action='store_true',
            help='Be more quiet')

    g_gen = parser.add_argument_group('CW Generation')
    g_gen.add_argument('--normalise-special-characters', action='store_true',
            help='Normalise special characters, like á to a')
    g_gen.add_argument('--frequency', type=int, default=600,
            help='Tone frequency in Hz (default: 600)')
    g_gen.add_argument('--wpm', type=int, default=12,
            help='Initial speed in WPM (default: 12)')
    g_gen.add_argument('--length-standard-deviation', type=float, default=0.0,
            help='Standard deviation from dotlength, '
                'relative to the dot length (default: 0.0; sensible: < 0.2)')
    g_gen.add_argument('--length-drift', type=float, default=0.0,
            help='Speed drift (default: 0.0; suggested: 0.02)')

    g_noise = parser.add_argument_group('Noise Generation')
    g_noise.add_argument('--noise-kind', type=str, default='white',
            help='Noise kind (default: white; other values: pink, blue, brown, violet)')
    g_noise.add_argument('--noise-level', type=float, default=0.0,
            help='Add noise with this amplitude (0 <= a <= 1; default: 0)')

    args = parser.parse_args()

    if not args.quiet:
        print('cwgen.py  Copyright (C) 2018  Camil Staps')
        print('This program comes with ABSOLUTELY NO WARRANTY.')
        print('This is free software, and you are welcome to redistribute it under certain conditions.')
        print('See the LICENSE file for details.')

    gen = CWGenerator(
            wpm=args.wpm,
            length_standard_deviation=args.length_standard_deviation,
            length_drift=args.length_drift)
    stream = gen.produce(args.input.read())
    if args.wave is not None:
        wav = wave.open(args.wave)
        wav.setnchannels(1)
        wav.setsampwidth(SAMPWIDTH)
        wav.setframerate(FRAMERATE)

        max_amp = int(2 ** (8 * SAMPWIDTH - 1)) - 1

        for on, duration in stream:
            audio = sine_wave(
                    frequency=args.frequency,
                    amplitude=0.5 if on else 0.0)
            if args.noise_level > 0.0:
                audio = mix(audio, noise_generator(args.noise_kind, args.noise_level))
            audio = itertools.islice(audio, int(duration * FRAMERATE / 1000))
            audio = b''.join(struct.pack('h', int(max_amp * a)) for a in audio)
            wav.writeframes(audio)

if __name__ == '__main__':
    main()
