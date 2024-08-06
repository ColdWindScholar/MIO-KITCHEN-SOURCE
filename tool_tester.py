import unittest
import os
import sys

if os.name == 'nt':
    prog_path = os.getcwd()
else:
    prog_path = os.path.normpath(os.path.abspath(os.path.dirname(sys.argv[0])))


class Test(unittest.TestCase):
    def setUp(self):
        print(
            'Starting Test.'
        )

    def test_import(self):
        pys = [i[:-3] for i in os.listdir(prog_path) if i.endswith('.py') and i != 'build.py']
        pys.append('tkinter')
        pys.remove('tool')
        sys.path.append(prog_path)
        for i in pys:
            print(f'Importing {i}')
            __import__(i)

    def tearDown(self):
        print('Test Done!')


if __name__ == '__main__':
    unittest.main()
else:
    test_main = unittest.main
