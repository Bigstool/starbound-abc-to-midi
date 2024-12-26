import re
import os
import argparse
import pretty_midi

from fractions import Fraction


class Metadata:
    def __init__(self):
        self.tempo = 2  # Seconds per whole note
        # self.time_signature = Fraction('4/4')
        self.key = 0  # -7 to 7
        self.accidentals = {}  # {note: accidental} e.g., {'C': 1, 'F,,': -1}
        self.default_note_length = Fraction('1/4')  # Default note value

    def reset_accidentals(self):
        """
        Reset the accidentals dictionary in the metadata.

        :return: None
        """
        self.accidentals = {}


def parse_abc_note(metadata: Metadata, note: str):
    """
    Parse an ABC note into its components: pitch, accidental, octave, and value.

    :param metadata: A Metadata object
    :param note: A string representing an ABC note
    :return: A dictionary containing the components of the note
    """
    # Define the regex for parsing the note
    note_regex = re.compile(
        r"""
        ^
        (?P<accidental>\^+|=|_+)?        # Accidental: ^^, ^, =, _, __ or none
        (?P<pitch>[A-Za-gz])             # Pitch: A to G (case-sensitive)
        (?P<octave>[,']*)                # Octave markers: zero or more , or '
        (?P<value>\d*/\d*|\d+)?          # Value: integer, fraction, or none
        $                                # End of string
        """,
        re.VERBOSE
    )

    # Match the note against the regex
    match = note_regex.match(note)
    if not match:
        raise ValueError(f"Invalid ABC note: {note}")

    # Extract the components using named groups
    components = match.groupdict()

    # Normalize the value component
    value = components['value']
    if value is None:
        components['value'] = '1'  # Default to a whole note if value is None
    elif '/' in value:
        if value == '/':
            components['value'] = '1/2'
        elif value.startswith('/'):
            components['value'] = f"1{value}"
        elif value.endswith('/'):
            components['value'] = f"{value}2"
    # Convert the value to a Fraction
    components['value'] = Fraction(components['value'])
    # Apply default note length
    components['value'] *= metadata.default_note_length

    return components


def parse_abc_chord(chord):
    """
    Parse an ABC chord into a list of individual notes.

    :param chord: A string representing an ABC chord
    :return: A list of strings, each representing an ABC note
    """
    # Split the chord into individual notes using a refined regex
    note_regex = re.compile(
        r"""
        (\^+|=|_+)?                  # Accidental: ^^, ^, =, _, __ or none
        [A-Ga-gz]                    # Pitch: A to G, z (case-sensitive, z for rest)
        [,']*                        # Octave markers: zero or more , or '
        (\d*/\d*|\d+)?               # Value: integer, fraction, or none
        """,
        re.VERBOSE
    )

    # Find all matches for individual notes in the chord
    notes = [match.group() for match in note_regex.finditer(chord)]
    if not notes:
        raise ValueError(f"Invalid ABC chord: {chord}")
    return notes


def get_midi_pitch(metadata: Metadata, accidental: None | str, pitch: str, octave: str) -> int:
    """
    Convert an ABC pitch to a MIDI pitch number. Does not modify the metadata object.

    :param metadata: A Metadata object containing the key signature and accidentals
    :param accidental: A string representing the accidental of the note
    :param pitch: A string representing the pitch of the note
    :param octave: A string representing the octave of the note
    :return: An integer representing the MIDI pitch number of the note
    """
    # Define the pitch classes as MIDI note numbers
    pitch_classes = {
        'C': 60, 'D': 62, 'E': 64, 'F': 65, 'G': 67, 'A': 69, 'B': 71,
        'c': 72, 'd': 74, 'e': 76, 'f': 77, 'g': 79, 'a': 81, 'b': 83
    }
    # Define one octave and octave shift direction
    one_octave = 12
    octave_direction = 0  # 0 if none
    if len(octave) > 0:
        octave_direction = 1 if octave[0] == "'" else -1  # 1 if ', -1 if ,
    # Check accidental -> pitch to MIDI note number -> either apply accidentals or key signature
    # If accidental is not None, update the accidentals dictionary in the metadata
    if accidental is not None:
        if accidental == '=':
            metadata.accidentals[f'{pitch}{octave}'] = 0
        else:
            accidental_direction = 1 if accidental.startswith('^') else -1  # 1 if ^, -1 if _
            metadata.accidentals[f'{pitch}{octave}'] = accidental_direction * len(accidental)
    # Convert the pitch to a MIDI note number
    midi_pitch = pitch_classes[pitch] + octave_direction * one_octave * len(octave)
    # Either apply the accidental or the key signature
    if f'{pitch}{octave}' in metadata.accidentals:
        midi_pitch += metadata.accidentals[f'{pitch}{octave}']
    else:
        if metadata.key >= 1 and pitch.upper() == 'F' or \
                metadata.key >= 2 and pitch.upper() == 'C' or \
                metadata.key >= 3 and pitch.upper() == 'G' or \
                metadata.key >= 4 and pitch.upper() == 'D' or \
                metadata.key >= 5 and pitch.upper() == 'A' or \
                metadata.key >= 6 and pitch.upper() == 'E' or \
                metadata.key >= 7 and pitch.upper() == 'B':
            midi_pitch += 1
        if metadata.key <= -1 and pitch.upper() == 'B' or \
                metadata.key <= -2 and pitch.upper() == 'E' or \
                metadata.key <= -3 and pitch.upper() == 'A' or \
                metadata.key <= -4 and pitch.upper() == 'D' or \
                metadata.key <= -5 and pitch.upper() == 'G' or \
                metadata.key <= -6 and pitch.upper() == 'C' or \
                metadata.key <= -7 and pitch.upper() == 'F':
            midi_pitch -= 1
    return midi_pitch


def parse_meta_key(metadata: Metadata, line: str):
    """
    Parse an ABC key signature into a number of sharps or flats. Modifies the metadata object in place.

    :param metadata: A Metadata object
    :param line: A string representing an ABC key signature (e.g., 'C', 'F#', 'Bb', 'Eb')
    :return: None
    """
    # Lookup table for converting key signatures to number of sharps or flats
    key_accidentals = {
        'Cb': -7, 'Gb': -6, 'Db': -5, 'Ab': -4, 'Eb': -3, 'Bb': -2, 'F': -1,
        'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7
    }
    metadata.key = key_accidentals[line]
    # Reset the accidentals dictionary in the metadata TODO: unsure if this should be done
    metadata.reset_accidentals()


def parse_tempo(metadata: Metadata, line: str):
    """
    Parse an ABC tempo into a tempo in seconds per whole note. Modifies the metadata object in place.

    :param metadata: A Metadata object
    :param line: A string representing an ABC tempo (e.g., '1=120', '1/4=120', '1/8=120', '1/16=120', '120', '60')
    :return: None
    """
    tempo_regex = re.compile(
        r"""
        ^
        ((?P<unit>\d+/\d+|\d+)=)?        # Accidental: ^^, ^, =, _, __ or none
        (?P<bpm>\d+)                     # Pitch: A to G (case-sensitive)
        $                                # End of string
        """,
        re.VERBOSE
    )
    # Match the note against the regex
    match = tempo_regex.match(line)
    if not match:
        raise ValueError(f"Invalid ABC tempo: {line}")

    # Extract the components using named groups
    components = match.groupdict()
    if components['unit'] is None:  # Default to 1/4 if unit is None
        components['unit'] = '1/4'

    # Convert to seconds per whole note
    metadata.tempo = 60 / int(components['bpm']) / Fraction(components['unit'])


def abc_to_piano_roll(abc: list[str]) -> list[list]:
    """
    Convert an ABC song to a piano roll.

    :param abc: A list of strings representing an ABC song.
    :return: A list of lists in the form of [[start: float, end: float, pitch: int, velocity: int], ...]
    """
    piano_roll: list[list] = []  # [[start: float, end: float, pitch: int, velocity: int], ...]
    metadata = Metadata()
    seconds_elapsed = 0  # Number of seconds elapsed before the last tempo change
    beats_elapsed: Fraction = Fraction('0')  # Number of beats elapsed after the last tempo change

    for line in abc:
        # Get rid of tailing comments (e.g., `% foo`), then strip whitespace
        line = re.sub(r'%.+$', '', line).strip()
        # Skip empty lines
        if not line:
            continue
        # Process metadata
        if re.match(r'^[A-Z]:', line):  # Metadata line starts with a capital letter followed by a colon
            # Get metadata type
            metadata_type = line[0]
            # Get rid of beginning metadata type (e.g., `X:`), then strip whitespace
            line = re.sub(r'^[A-Z]:', '', line).strip()
            # Process metadata
            if metadata_type == 'K':  # Key signature
                parse_meta_key(metadata, line)
            if metadata_type == 'Q':  # Tempo
                # Save bets_elapsed into seconds_elapsed
                seconds_elapsed += metadata.tempo * beats_elapsed
                # Reset beats_elapsed
                beats_elapsed = Fraction('0')
                # Update tempo
                parse_tempo(metadata, line)
            if metadata_type == 'L':  # Default note length
                metadata.default_note_length = Fraction(line)
            continue  # No applicable metadata, so skip to the next line
        # Process notes
        # Split the line into individual notes and chords
        notes = line.split(' ')
        for item in notes:
            # Convert notes into chords of one note
            if not item.startswith('['):
                item = f"[{item}]"
            # Parse the chord into individual notes
            chord = parse_abc_chord(item)
            # Parse the individual notes into components
            chord = [parse_abc_note(metadata, note) for note in chord]
            # Process each note in the chord
            for components in chord:
                # Skip rests
                if components['pitch'] == 'z':
                    continue
                # Convert the pitch to a MIDI pitch number
                pitch = get_midi_pitch(metadata, components['accidental'], components['pitch'], components['octave'])
                # Calculate the start and end times of the note
                start_time = seconds_elapsed + (metadata.tempo * beats_elapsed)
                end_time = start_time + (metadata.tempo * components['value'])
                # Add the note to the piano roll
                piano_roll.append([start_time, end_time, pitch, 80])
            # Update the number of beats elapsed with the smallest note value in the chord
            beats_elapsed += min([note['value'] for note in chord])

    return piano_roll


def piano_roll_to_midi(piano_rolls: list[list[list]]) -> pretty_midi.PrettyMIDI:
    """
    Convert a list of piano rolls to a MIDI file. Each piano roll will be converted to a separate track.

    :param piano_rolls: A list of piano rolls
                        Each piano roll is in the form of [[start: float, end: float, pitch: int, velocity: int], ...]
    :return: A PrettyMIDI object
    """
    mid = pretty_midi.PrettyMIDI(resolution=480, initial_tempo=120.0)
    for piano_roll in piano_rolls:
        track = pretty_midi.Instrument(program=pretty_midi.instrument_name_to_program('Acoustic Grand Piano'))
        for note in piano_roll:
            start_time, end_time, pitch, velocity = note
            track.notes.append(pretty_midi.Note(
                velocity=velocity,
                pitch=pitch,
                start=start_time,
                end=end_time
            ))
        mid.instruments.append(track)
    return mid


def convert_songs(songs_dir: str, output_dir: str):
    """
    Convert a directory of ABC songs to MIDI files.

    :param songs_dir: The directory containing the ABC songs
    :param output_dir: The directory to save the MIDI files
    :return: None
    """
    # Create the output directory if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # Process each song in the songs directory
    for song_file in os.listdir(songs_dir):
        # Skip non-ABC files
        if not song_file.endswith('.abc'):
            continue
        # Load the song from the file
        with open(os.path.join(songs_dir, song_file), 'r') as file:
            abc = [line.strip() for line in file]
        try:
            # Convert the song to a piano roll
            piano_roll = abc_to_piano_roll(abc)
            # Convert the piano roll to a MIDI file
            mid = piano_roll_to_midi([piano_roll])
            # Save the MIDI file
            mid.write(os.path.join(output_dir, f"{os.path.splitext(song_file)[0]}.mid"))
        except (ValueError, Exception) as e:
            print(f"Error processing {song_file}: {e}")


def convert_and_combine_songs(song_paths: list[str], output_path: str):
    """
    Convert a list of ABC songs to MIDI files and combine them into a single MIDI file.

    :param song_paths: A list of paths to ABC songs
    :param output_path: The path to save the combined MIDI file
    :return: None
    """
    # Convert each song to a piano roll
    piano_rolls = []
    for song_path in song_paths:
        with open(song_path, 'r') as file:
            abc = [line.strip() for line in file]
        try:
            piano_roll = abc_to_piano_roll(abc)
            piano_rolls.append(piano_roll)
        except (ValueError, Exception) as e:
            print(f"Error processing {song_path}: {e}")
    # Convert the piano rolls to MIDI files
    mid = piano_roll_to_midi(piano_rolls)
    # Save the combined MIDI file
    mid.write(output_path)


def test():
    # Test parse_abc_note
    notes = ['z/16', '_D/4', 'f', 'B,/4', 'd/4', 'A,,3/', '^C', '^^B,,/4', "c", "_E'3", "G/", "=F,,2", "B"]
    for note in notes:
        try:
            metadata = Metadata()
            metadata.default_note_length = Fraction('1')
            print(f"{note} -> {parse_abc_note(metadata, note)}")
        except ValueError as e:
            print(e)
    # Test parse_abc_chord
    # chord = '[z/16_D/4fB,/4d/4A,,3/^C]'
    chord = '[z/16_D/4fB,/4d/4A,,3/^C^^B,,/4c_E\'3G/=F,,2B]'
    try:
        print(f"{chord} -> {parse_abc_chord(chord)}")
    except ValueError as e:
        print(e)
    # Test parse_tempo
    tempos = ['1=120', '1/4=120', '1/8=120', '1/16=120', '120', '60']
    for tempo in tempos:
        try:
            metadata = Metadata()
            parse_tempo(metadata, tempo)
            print(f"{tempo} -> {metadata.tempo}")
        except ValueError as e:
            print(e)
    # Test abc_to_piano_roll
    with open('res/songs/On The Beach - Piano.abc', 'r') as file:
        abc = [line.strip() for line in file]
    piano_roll = abc_to_piano_roll(abc)
    mid = piano_roll_to_midi(piano_roll)
    mid.write('res/On The Beach - Piano.mid')


def main():
    # Command-line arguments for --convert-songs and --convert-and-combine
    parser = argparse.ArgumentParser(description="Convert ABC songs to MIDI files")
    subparsers = parser.add_subparsers(dest='command', required=True)
    # For --convert-songs, specify the songs directory --songs-dir and the output directory --output-dir
    convert_songs_parser = subparsers.add_parser(
        'convert-songs',
        description="Bulk convert a directory of ABC songs to MIDI files"
    )
    convert_songs_parser.add_argument('--songs-dir', type=str, required=True,
                                      help="The directory containing the ABC songs")
    convert_songs_parser.add_argument('--output-dir', type=str, required=True,
                                      help="The directory to save the MIDI files")
    # For --convert-and-combine,
    # specify the song paths --song-paths (accepts multiple paths) and the output path --output-path
    convert_and_combine_parser = subparsers.add_parser(
        'convert-and-combine',
        description="Convert and combine one or more ABC song(s) into a single MIDI file as separate tracks"
    )
    convert_and_combine_parser.add_argument('--song-paths', type=str, nargs='+', required=True,
                                            help="The paths to one or more ABC song(s)")
    convert_and_combine_parser.add_argument('--output-path', type=str, required=True,
                                            help="The path to save the combined MIDI file")
    args = parser.parse_args()
    # Convert songs
    if args.command == 'convert-songs':
        convert_songs(songs_dir=args.songs_dir, output_dir=args.output_dir)
    # Convert and combine songs
    if args.command == 'convert-and-combine':
        convert_and_combine_songs(song_paths=args.song_paths, output_path=args.output_path)


if __name__ == '__main__':
    # test()
    # convert_songs(songs_dir='./res/songs', output_dir='./res/songs_midi')
    # song_paths = [
    #     'res/songs/On The Beach - Piano.abc',
    #     'res/songs/On The Beach - Violin.abc',
    #     'res/songs/On The Beach - Oboe.abc'
    # ]
    # convert_and_combine_songs(song_paths=song_paths, output_path='res/On The Beach.mid')
    main()
