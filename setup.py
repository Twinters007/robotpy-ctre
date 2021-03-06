
#
# Much of this copied from https://github.com/pybind/python_example.git
#

from os.path import dirname, exists, join
from setuptools import find_packages, setup, Extension
from setuptools.command.build_ext import build_ext
import subprocess
import sys
import setuptools

setup_dir = dirname(__file__)
git_dir = join(setup_dir, '.git')
base_package = 'ctre'
version_file = join(setup_dir, base_package, 'version.py')

# Automatically generate a version.py based on the git version
if exists(git_dir):
    p = subprocess.Popen(["git", "describe", "--tags", "--long", "--dirty=-dirty"],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    # Make sure the git version has at least one tag
    if err:
        print("Error: You need to create a tag for this repo to use the builder")
        sys.exit(1)

    # Convert git version to PEP440 compliant version
    # - Older versions of pip choke on local identifiers, so we can't include the git commit
    v, commits, local = out.decode('utf-8').rstrip().split('-', 2)
    if commits != '0' or '-dirty' in local:
        v = '%s.post0.dev%s' % (v, commits)

    # Create the version.py file
    with open(version_file, 'w') as fp:
        fp.write("# Autogenerated by setup.py\n__version__ = '{0}'".format(v))

if exists(version_file):
    with open(join(setup_dir, base_package, 'version.py'), 'r') as fp:
        exec(fp.read(), globals())
else:
    __version__ = 'master'

with open(join(setup_dir, 'README.rst'), 'r') as readme_file:
    long_description = readme_file.read()


#
# pybind-specific compilation stuff
#

class get_pybind_include(object):
    """Helper class to determine the pybind11 include path

    The purpose of this class is to postpone importing pybind11
    until it is actually installed, so that the ``get_include()``
    method can be invoked. """

    def __init__(self, user=False):
        self.user = user

    def __str__(self):
        import pybind11
        return pybind11.get_include(self.user)

# As of Python 3.6, CCompiler has a `has_flag` method.
# cf http://bugs.python.org/issue26689
def has_flag(compiler, flagname):
    """Return a boolean indicating whether a flag name is supported on
    the specified compiler.
    """
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.cpp') as f:
        f.write('int main (int argc, char **argv) { return 0; }')
        try:
            compiler.compile([f.name], extra_postargs=[flagname])
        except setuptools.distutils.errors.CompileError:
            return False
    return True


def cpp_flag(compiler):
    """Return the -std=c++[11/14] compiler flag.

    The c++14 is prefered over c++11 (when it is available).
    """
    if has_flag(compiler, '-std=c++14'):
        return '-std=c++14'
    elif has_flag(compiler, '-std=c++11'):
        return '-std=c++11'
    else:
        raise RuntimeError('Unsupported compiler -- at least C++11 support '
                           'is needed!')


class BuildExt(build_ext):
    """A custom build extension for adding compiler-specific options."""
    c_opts = {
        'msvc': ['/EHsc'],
        'unix': [],
    }

    if sys.platform == 'darwin':
        c_opts['unix'] += ['-stdlib=libc++', '-mmacosx-version-min=10.7']

    def build_extensions(self):
        ct = self.compiler.compiler_type
        opts = self.c_opts.get(ct, [])
        if ct == 'unix':
            opts.append('-DVERSION_INFO="%s"' % self.distribution.get_version())
            opts.append('-s') # strip
            opts.append('-g0') # remove debug symbols
            opts.append(cpp_flag(self.compiler))
            if has_flag(self.compiler, '-fvisibility=hidden'):
                opts.append('-fvisibility=hidden')
        elif ct == 'msvc':
            opts.append('/DVERSION_INFO=\\"%s\\"' % self.distribution.get_version())
        for ext in self.extensions:
            ext.extra_compile_args = opts
        build_ext.build_extensions(self)


install_requires = ['wpilib>=2017.0.0,<2018.0.0']

# Detect roboRIO.. not foolproof, but good enough
if exists('/etc/natinst/share/scs_imagemetadata.ini'):
    
    # Download/install the CTRE and HAL binaries necessary to compile
    # -> must have robotpy-hal-roborio installed for this to work
    import hal_impl.distutils
    
    # no version info available
    url = 'http://www.ctr-electronics.com//downloads/lib/CTRE_FRCLibs_NON-WINDOWS.zip'
    
    halsrc = hal_impl.distutils.extract_halzip()
    zipsrc = hal_impl.distutils.download_and_extract_zip(url)
    
    ext_modules = [
        Extension(
            'ctre._impl.cantalon_roborio',
            ['ctre/_impl/cantalon_roborio.cpp'],
            include_dirs=[
                # Path to pybind11 headers
                get_pybind_include(),
                get_pybind_include(user=True),
                join(halsrc, 'include'),
                join(zipsrc, 'cpp', 'include'),
            ],
            libraries=['HALAthena', 'TalonSRXLib'],
            library_dirs=[
                join(halsrc, 'lib'),
                join(zipsrc, 'cpp', 'lib'),
            ],
            language='c++',
        ),
    ]
    
    # This doesn't actually work, as it needs to be installed before setup.py is ran
    # ... but we specify it 
    #install_requires = ['pybind11>=1.7']
    install_requires.append('robotpy-hal-roborio>=2017.0.2,<2018.0.0')
    cmdclass = {'build_ext': BuildExt}
else:
    install_requires.append('robotpy-hal-sim>=2017.0.2,<2018.0.0')
    ext_modules = None
    cmdclass = {}

setup(
    name='robotpy-ctre',
    version=__version__,
    author='Dustin Spicuzza',
    author_email='dustin@virtualroadside.com',
    url='https://github.com/robotpy/robotpy-ctre',
    description='RobotPy bindings for CTRE third party libraries',
    long_description=long_description,
    packages=find_packages(),
    ext_modules=ext_modules,
    install_requires=install_requires,
    cmdclass=cmdclass,
    zip_safe=False,
)
