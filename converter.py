import re
import pretty_midi


class Metadata:
    def __init__(self):
        # TODO: note value is (numerator, denominator)
        # TODO: hence note duration is self.tempo * (numerator / denominator)
        self.tempo = 2  # Seconds per whole note
        # self.time_signature = (4, 4)
        # TODO: if self.key >= 1 and note.letter_name == 'F': note.accidental = 1
        self.key = 0  # -7 to 7
        # TODO: first if note has accidental, add or update self.accidentals
        # TODO: then convert abc pitch to midi note number,
        # TODO: then if pitch in accidentals: ... else: (apply key signature)
        self.accidentals = {}  # {note: accidental} e.g., {'C': 1, 'F,,': -1}


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


def converter(abc: str) -> list[list]:
    playhead = 0  # Start time of the current note in seconds


def test():
    # Example usage
    notes = ['z/16', '_D/4', 'f', 'B,/4', 'd/4', 'A,,3/', '^C', '^^B,,/4', "c", "_E'3", "G/", "=F,,2", "B"]
    for note in notes:
        try:
            print(f"{note} -> {parse_abc_note(note)}")
        except ValueError as e:
            print(e)

    chord = '[z/16_D/4fB,/4d/4A,,3/^C]'
    try:
        print(f"{chord} -> {parse_abc_chord(chord)}")
    except ValueError as e:
        print(e)

    # TODO: parse metadata: get rid of beginning (e.g., `X:`) and any comments (e.g., `% foo`), then strip whitespace


if __name__ == '__main__':
    test()
