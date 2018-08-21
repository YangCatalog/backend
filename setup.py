from setuptools import setup, find_packages

setup(
    name='yang',
    version='',
    packages=find_packages(),
    url='',
    license='',
    author='Miroslav Kovac',
    author_email='',
    description='',
    install_requires=['numpy;python_version<"3.4"',  'pytest;python_version<"3.4"',
                      'travispy;python_version<"3.4"', 'flask;python_version<"3.4"', 'Crypto;python_version<"3.4"', 'pika;python_version<"3.4"',
                      'urllib3;python_version<"3.4"', 'pyOpenSSL;python_version<"3.4"', 'flask-httpauth;python_version<"3.4"',
                      'configparser;python_version>"3.4"',
                      'requests', 'jinja2', 'pyang', 'gitpython', 'ciscosparkapi', 'mysqlclient'
                      ]
)
