import py_compile
import os

for path in [
    os.path.join('SRC', 'main.py'),
    os.path.join('SRC', '__main__.py'),
    os.path.join('SRC', '__init__.py'),
]:
    py_compile.compile(path, doraise=True)
    print('ok', path)
