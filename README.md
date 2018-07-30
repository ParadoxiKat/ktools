# ktools

ktools -- Katie's collection of useful tools

Various modules and functions that are useful across projects.
## ktools.config
Config file loader
* Loads multiple json-formatted config files from various disk locationsssss, and presents them as a dict.
* Tries loading from program directory, accounting for being frozen. Then from various user-config locations.
* Can optionally have values set from command line args
* If used with ProgWrapper (See below), can optionally add -c and -C command line arguments. These options add additional config files, or replace all configs from a new config file ,respectively.
## ktools.log
Custom logging facility for programs using ProgWrapper (See below)
* Adds logging options to the command line.
* Can optionally handle rotation of old logs, including compressing old files.
## ktools.progwrapper
A context manager to call your main function from.
* Can be configured to include argument parsing, config file loading, and logging setup.
* Provides an opts dict within the context manager (with progwrapper(...) as opts:), containing the parser, the config object from ktools.config, and various other pieces of info such as paths.
* Can be configured to perform certain actions upon success, failure, or completion of your main function.
* Can email logs or other data at the end of program execution. This feature could be extended to upload the info via ftp or some other protocol.
## ktools.threadpool
A simple thread pool to perform asyncronace tasks
* Pool can be resized on the fly
* TODO: document this better. 
## ktools.utils
Assortment of miscellaneous odd functions I've written or found and tweaked over the years
* TODO: Document this better