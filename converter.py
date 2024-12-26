import re
import pretty_midi

from fractions import Fraction


class Metadata:
    def __init__(self):
        # TODO: note value is (note.num/note.den) * (default_note_length.num/default_note_length.den)
        # TODO: hence note duration is self.tempo * note_value
        self.tempo = 2  # Seconds per whole note
        # self.time_signature = Fraction('4/4')
        self.key = 0  # -7 to 7
        self.accidentals = {}  # {note: accidental} e.g., {'C': 1, 'F,,': -1}
        self.default_note_length = Fraction('1/4')  # Default note value


def parse_abc_note(note):
    """
    Parse an ABC note into its components: pitch, accidental, octave, and value.

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
    Convert an ABC pitch to a MIDI pitch number.

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
        if metadata.key >= 1 and pitch == 'F' or \
                metadata.key >= 2 and pitch == 'C' or \
                metadata.key >= 3 and pitch == 'G' or \
                metadata.key >= 4 and pitch == 'D' or \
                metadata.key >= 5 and pitch == 'A' or \
                metadata.key >= 6 and pitch == 'E' or \
                metadata.key >= 7 and pitch == 'B':
            midi_pitch += 1
        if metadata.key <= -1 and pitch == 'B' or \
                metadata.key <= -2 and pitch == 'E' or \
                metadata.key <= -3 and pitch == 'A' or \
                metadata.key <= -4 and pitch == 'D' or \
                metadata.key <= -5 and pitch == 'G' or \
                metadata.key <= -6 and pitch == 'C' or \
                metadata.key <= -7 and pitch == 'F':
            midi_pitch -= 1
    return midi_pitch


def parse_meta_key(metadata: Metadata, line: str):
    # Lookup table for converting key signatures to number of sharps or flats
    key_accidentals = {
        'Cb': -7, 'Gb': -6, 'Db': -5, 'Ab': -4, 'Eb': -3, 'Bb': -2, 'F': -1,
        'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7
    }
    metadata.key = key_accidentals[line]


def parse_tempo(metadata: Metadata, line: str):
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
    piano_roll: list[list] = []  # [[start: float, end: float, pitch: int, velocity: int], ...]
    metadata = Metadata()
    # TODO: start_time = seconds_elapsed + (metadata.tempo * beats_elapsed)
    # TODO: end_time = start_time + (metadata.tempo * note_value)
    # TODO: note_value = (note.num/note.den) * (default_note_length.num/default_note_length.den)
    seconds_elapsed = 0  # Number of seconds elapsed before the last tempo change
    beats_elapsed: Fraction = Fraction('0')  # Number of beats elapsed after the last tempo change

    for line in abc:
        # Skip empty lines
        if not line:
            continue
        # Process metadata
        if re.match(r'^[A-Z]:', line):  # Metadata line starts with a capital letter followed by a colon
            # Get metadata type
            metadata_type = line[0]
            # Get rid of beginning (e.g., `X:`) and any comments (e.g., `% foo`), then strip whitespace
            line = re.sub(r'^[A-Z]:|%.+$', '', line).strip()
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


    return piano_roll


def piano_roll_to_midi(piano_roll: list[list]) -> pretty_midi.PrettyMIDI:
    pass


def test():
    # Test parse_abc_note
    notes = ['z/16', '_D/4', 'f', 'B,/4', 'd/4', 'A,,3/', '^C', '^^B,,/4', "c", "_E'3", "G/", "=F,,2", "B"]
    for note in notes:
        try:
            print(f"{note} -> {parse_abc_note(note)}")
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

    # # Test read file
    # with open('On The Beach - Piano.abc', 'r') as file:
    #     abc = [line.strip() for line in file]
    # abc_to_piano_roll(abc)



if __name__ == '__main__':
    test()
