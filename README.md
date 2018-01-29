# cwgen.py
Generate CW audio files from text

## Typical usage

```bash
./cwgen.py \
	--text 'cqcqdepa5et pa5etk' \
	--wpm 12 \
	--frequency 650 \
	--length-standard-deviation 0.05 \
	--length-drift 0.02 \
	--noise-kind pink \
	--noise-level 0.3 \
	--play
```

For more options and their explanation, see `./cwgen.py --help`.

## Legal info

Copyright &copy; 2018 Camil Staps.
Licensed under GNU GPL v3.
For more details, see the LICENSE file.
