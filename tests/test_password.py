
from ats.kyaraben.password import generate_password

import unittest


class PasswordTest(unittest.TestCase):
    def test_empty(self):
        self.assertEquals(generate_password(0), '')

    def test_length(self):
        for x in range(100):
            self.assertEquals(len(generate_password(x)), x)
