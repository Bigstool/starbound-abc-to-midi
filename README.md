# Starbound ABC to MIDI converter

Converts Starbound style ABC tunes into MIDI files.

## Dependencies

- `Python=3.10`
- `pretty_midi==0.2.10`

## Usage

First, locate your Starbound installation directory. The ABC files are in the `Starbound/assets/user/songs` directory under the installation directory.

The usage of `convert.py` is as follows:

### Bulk convert the ABC files in the `songs` directory into MIDI file

```sh
python convert.py convert-songs --songs-dir <songs_dir_path> --output-dir <output_dir_path>
```

example:

```sh
python convert.py convert-songs --songs-dir /path/to/Starbound/assets/user/songs --output-dir ./songs_midi
```

### Convert and combine one or more ABC song(s) into a single MIDI file as separate tracks

```sh
python convert.py convert-and-combine --song-paths <song_abc_path> [<song_abc_path> ...] --output-path <output_mid_path>
```

example:

```sh
python convert.py convert-and-combine --song-paths "path/to/songs/On The Beach - Piano.abc" "path/to/songs/On The Beach - Violin.abc" "path/to/songs/On The Beach - Oboe.abc" --output-path "./On The Beach.mid"
```

## Limitations

This script is developed closely around the ABC files that come with the Starbound game. It might not work for other ABC files. Most notably, it:

- Does not handle bar lines
- Does not handle transpositions
- Does not reflect time signature, key signature, and bar lines in the converted MIDI file

Currently, the following files from Starbound cannot be converted due to the limitations mentioned above:

- Awake Sweet Love.abc
- Bourree.abc
- Sarabande.abc
- Sonata Zapateado.abc

Additionally, the transpositions comments in the files will be ignored, and the file will be converted w.r.t. the key signature information fields.