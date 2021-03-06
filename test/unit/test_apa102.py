"""
test/unit/test_apa102.py

Unit tests for the main apa102 module.

See LICENSE.txt for more details.
"""
import gpiod
import unittest
from unittest.mock import patch

import apa102_gpiod.apa102 as apa102


class TestMiscFunctions(unittest.TestCase):
    """
    Test class to test the miscellaneous functions in the apa102 module.
    """
    def test_check_ledoutput_range_raises_valueerror_on_invalid_arguments(self):
        test_ranges = {
            'brightness': (-10, 50),
            'red': (-10, 0x10f),
            'green': (-10, 0x10f),
            'blue': (-10, 0x10f)
        }
        indices = {
            'brightness': 0,
            'red': 1,
            'green': 2,
            'blue': 3
        }
        valid_ranges = {
            'brightness': range(32),
            'red': range(0x100),
            'green': range(0x100),
            'blue': range(0x100)
        }
        for (tested_component, (rs, rend)) in test_ranges.items():
            for i in range(rs, rend, 1):
                output = [0, 0, 0, 0]
                output[indices[tested_component]] = i
                if i not in valid_ranges[tested_component]:
                    with self.assertRaisesRegex(ValueError,
                                                '.*?' + tested_component
                                                + ' setting invalid'):
                        apa102._check_ledoutput_range(apa102.LedOutput(*output))
                else:
                    apa102._check_ledoutput_range(apa102.LedOutput(*output))

            # Test that ValueError is also raised for non-integer types
            with self.assertRaisesRegex(ValueError,
                                        '.*?' + tested_component
                                        + ' setting invalid'):
                output = [0, 0, 0, 0]
                output[indices[tested_component]] = float(
                    valid_ranges[tested_component][0])
                apa102._check_ledoutput_range(apa102.LedOutput(*output))

    def test_check_generate_end_sequence_returns_correct_result(self):
        # We expect at least one clock edge for each LED, except the first one,
        # where zero edges are required.
        edges_per_byte = 16  # Each byte sent to the LEDs provides us two edges
        for i in range(1000):
            edges_required = (i - 1) if i else 0
            end_sequence = apa102._generate_end_sequence(i)
            self.assertIsInstance(end_sequence, bytes)
            self.assertGreaterEqual(len(end_sequence)
                                    * edges_per_byte,
                                    edges_required)

    def test_check_pack_brgb_direct_correctly_packs_values(self):
        pack_target = bytearray(4)
        apa102._pack_brgb_direct(pack_target, 0x0f, 0xde, 0xad, 0xbe)
        self.assertSequenceEqual(pack_target,
                                 b'\xef\xbe\xad\xde')

    def test_check_pack_brgb_returns_correct_command_sequence(self):
        output = apa102.LedOutput(0x0f, 0xde, 0xad, 0xbe)
        packed = apa102._pack_brgb(output)
        self.assertSequenceEqual(packed,
                                 b'\xef\xbe\xad\xde')

    def test_check_led_output_from_led_command_returns_correct_ledoutput_tuple(
            self):
        output = apa102.LedOutput(11, 0xde, 0x11, 0xff)
        packed = apa102._pack_brgb(output)
        unpacked = apa102._ledoutput_from_led_command(packed)
        self.assertEquals(unpacked, output)


class TestAPA102(unittest.TestCase):
    """
    Test class containing test cases for the APA102 class.
    """

    def setUp(self):
        with patch('apa102_gpiod.apa102.gpiod.Chip',
                   autospec=True, spec_set=True) as mock_chip:
            self.instance = apa102.APA102('/dev/gpiochip0',
                                          8, 24, 23, False)
            self.mock_chip = mock_chip

    def test_init_magic_method_sets_up_gpio_lines(self):
        """
        Test that the __init__() magic method of the class sets up the
        GPIO lines used to control the APA102 LEDs.
        """
        self.mock_chip.assert_called_once_with('/dev/gpiochip0',
                                               self.mock_chip.OPEN_BY_PATH)
        self.mock_chip.return_value.get_lines.assert_called_once_with((24, 23))

        mock_lines = self.mock_chip.return_value.get_lines.return_value
        mock_lines.request.assert_called_once_with(
            'apa102_gpiod', gpiod.LINE_REQ_DIR_OUT, 0, (0, 0))

    def test_init_magic_method_correctly_zeroes_framebuffer_and_resets_leds(
            self):
        self.assertSequenceEqual(
            self.instance, [apa102.LedOutput(0, 0, 0, 0) for __ in range(8)])
        with patch('apa102_gpiod.apa102.gpiod.Chip', autospec=True,
                   spec_set=True) as __:
            with patch('apa102_gpiod.apa102.APA102.commit',
                       autospec=True, spec_set=True) as mock_commit:
                instance = apa102.APA102('/dev/gpiochip0',
                                         8, 24, 23, True)
                mock_commit.assert_called_once_with(instance)
                mock_commit.reset_mock()
                __ = apa102.APA102('/dev/gpiochip0', 8, 24, 23, False)
                mock_commit.assert_not_called()

    def test_getitem_setitem_magic_methods_raises_indexerror_on_invalid_index(
            self):
        output = apa102.LedOutput(1, 4, 5, 6)
        for i in range(-5, 12, 1):
            if (i >= 0) and (i < 8):
                __ = self.instance[i]
                self.instance[i] = output
            else:
                with self.assertRaisesRegex(IndexError, '.*? out-of-range'):
                    __ = self.instance[i]
                with self.assertRaisesRegex(IndexError, '.*? out-of-range'):
                    self.instance[i] = output

    def test_setitem_magic_method_raises_valueerror_on_invalid_ledoutput(self):
        # Since the _check_ledoutput_range() function is used to perform
        # checking on validity of the passed in item, we simply check if
        # __setitem__() calls this function. If it does, then it does
        # raise ValueError on invalid LedOutput named tuples passed to the
        # magic method, because the _check_ledoutput_range() function has
        # already been tested to do that.
        with patch('apa102_gpiod.apa102._check_ledoutput_range', autospec=True,
                   spec_set=True) as mock_check:
            self.setUp()
            mock_check.reset_mock()
            output = apa102.LedOutput(0, 0, 0, 0)
            self.instance[0] = output
            mock_check.assert_called_once_with(output)

    def test_setitem_getitem_magic_methods_correctly_sets_and_gets_item(self):
        # Since it uses set_brgb_unchecked() internally, the success of this
        # test also means that the set_brgb_unchecked() method succedded.
        output = apa102.LedOutput(1, 4, 5, 6)
        self.instance[0] = output
        self.assertEquals(self.instance[0], output)

    def test_len_magic_method_correctly_returns_number_of_controlled_leds(self):
        self.assertEquals(len(self.instance), 8)

    def test_contains_magic_method_returns_correct_result(self):
        output_present = apa102.LedOutput(5, 5, 5, 5)
        output_not_present = apa102.LedOutput(0, 123, 111, 200)
        for i in range(len(self.instance)):
            self.instance[i] = apa102.LedOutput(0, 0, 0, 0)

        self.instance[0] = output_present

        self.assertTrue((output_present in self.instance) is True)
        self.assertTrue((output_not_present in self.instance) is False)

    def test_commit_method_correctly_writes_bytes_to_leds(self):
        # Simply tests if a "sort-of" valid waveform is output on the I/O lines.
        # We expect that the data pin has already had the data value output
        # on it before the clock pin was raised to latch in the bit.
        # We expect 8 * len calls to set the clock pin high, to latch in
        # 8 * len bits. We expect the MSB to be clocked out first.
        waveform = []

        def record_line_state(state):
            waveform.append((state[0], state[1]))

        self.mock_chip.return_value.get_lines.return_value.set_values. \
            side_effect = record_line_state
        # Force commiting of data
        self.instance._data_modified = True
        self.instance.commit()
        test_int = int.from_bytes(self.instance._data, byteorder='big',
                                  signed=False)
        bit = (len(self.instance._data) * 8) - 1
        for t, (clock, data) in enumerate(waveform):
            # Ensure that we do not clock out too many bits
            self.assertGreaterEqual(bit, 0)
            if clock:
                # Ensure that the previous cycle had set the data line to the
                # correct state
                self.assertEqual(waveform[t - 1][1], (test_int >> bit) & 0x01)
                # Ensure that the clock line was low previously
                self.assertEqual(waveform[t - 1][0], 0)
                # Consider that one bit has been successfully clocked out
                bit -= 1
            else:
                # Assert that the data line is set to the correct state
                self.assertEqual(data, (test_int >> bit) & 0x01)

    def test_commit_method_correctly_commits_framebuffer_to_leds(self):
        # The system must have sent the following information
        # Start sequence
        # 4-byte sequence for each LED
        # End sequence
        waveform = []

        def record_line_state(state):
            waveform.append((state[0], state[1]))

        self.mock_chip.return_value.get_lines.return_value.set_values. \
            side_effect = record_line_state
        # Force commiting of data
        self.instance._data_modified = True
        self.instance.commit()
        payload = (apa102.APA102_START + b''.join([apa102._pack_brgb(o)
                                                   for o in self.instance])
                   + apa102._generate_end_sequence(len(self.instance)))

        payload_sent = 0
        bits_read = 0
        for t, (clock, data) in enumerate(waveform):
            if clock:
                # Read data line when clock line is high
                payload_sent <<= 1
                payload_sent |= data
                bits_read += 1
        self.assertEqual(bits_read % 8, 0)
        payload_sent_bytes = payload_sent.to_bytes(
            bits_read // 8, byteorder='big', signed=False)
        self.assertSequenceEqual(payload_sent_bytes, payload, bytes)

    def test_close_method_correctly_releases_resources(self):
        self.instance.close()
        self.mock_chip.return_value.get_lines.return_value.release. \
            assert_called_once_with()
        self.mock_chip.return_value.close.assert_called_once_with()
