import unittest
import components

class TestPartyFlipBitMethods(unittest.TestCase):

    def setUp(self):
        self.party = components.Party(0, "PartyName", None)

    def tearDown(self):
        del self.party

    def test_flip_bit_on_empty_key(self):
        with self.assertRaises(IndexError):
            self.party.flip_bit(0)

    def test_flip_bit_on_non_integer_char(self):
        self.party.sifted_key = "-"
        with self.assertRaises(ValueError):
            self.party.flip_bit(0)

    def test_flip_bit_on_non_binary_digit(self):
        self.party.sifted_key = "2"
        with self.assertRaises(ValueError):
            self.party.flip_bit(0)

    def test_flip_bit_on_binary_digit(self):
        self.party.sifted_key = "0"
        self.party.flip_bit(0)
        self.assertEqual(self.party.sifted_key, "1")

        self.party.sifted_key = "1"
        self.party.flip_bit(0)
        self.assertEqual(self.party.sifted_key, "0")

    def test_flip_bits_with_1bit_key_and_1bit_flip(self):
        self.party.sifted_key = "0"

        flip_bits_strs   = ["0", "x", "1", "0", "x", "1"]
        expected_results = ["0", "0", "1", "1", "1", "0"]

        for i in range(len(flip_bits_strs)):
            flip_bit_str = flip_bits_strs[i]
            expected_result = expected_results[i]

            self.party.flip_bits(flip_bit_str)
            self.assertEqual(self.party.sifted_key, expected_result)

    def test_flip_bits_with_2bit_key_and_2bit_flip(self):
        self.party.sifted_key = "00"

        flip_bits_strs   = ["0x", ".1", "10", "11"]
        expected_results = ["00", "01", "11", "00"]

        for i in range(len(flip_bits_strs)):
            flip_bits_str = flip_bits_strs[i]
            expected_result = expected_results[i]

            self.party.flip_bits(flip_bits_str)
            self.assertEqual(self.party.sifted_key, expected_result)

    def test_flip_bits_warnings(self):
        '''flip_bits should produce warnings when the given flip_bits_str is
        shorter or longer than the current sifted key.'''

        all_binary_strs_of_len_2 = ["00", "01", "10", "11"]
        all_binary_strs_of_len_3 = [(3 - len(bin(i)[2:])) * '0' + bin(i)[2:]
                                    for i in range(2 ** 3)]

        # Test on an empty sifted key
        self.party.sifted_key = ""
        test_flip_bits_strs = ["0", "1"]

        for flip_bits_str in test_flip_bits_strs:
            with self.assertWarns(Warning):
                self.party.flip_bits(flip_bits_str)

        # Test on 1-bit sifted keys
        test_sifted_keys = ["0", "1"]
        test_flip_bits_strs = [""] + all_binary_strs_of_len_2

        for sk in test_sifted_keys:
            self.party.sifted_key = sk
            for flip_bits_str in test_flip_bits_strs:
                with self.assertWarns(Warning):
                    self.party.flip_bits(flip_bits_str)

        # Test on 2-bit sifted keys
        test_sifted_keys = all_binary_strs_of_len_2
        test_flip_bits_strs = ["", "0", "1"] + all_binary_strs_of_len_3

        for sk in test_sifted_keys:
            self.party.sifted_key = sk
            for flip_bits_str in test_flip_bits_strs:
                with self.assertWarns(Warning):
                    self.party.flip_bits(flip_bits_str)

if __name__ == '__main__':
    unittest.main()
