Documentation
=============

##### Powered by slate

This package contains API documentation and description of yangcatalog.org
endpoints that can be used to search for modules

To generate html file you need to have:
* **Ruby, version 2.3.1 or newer**
* **Bundler** — If Ruby is already installed, but the bundle command
 doesn't work, just run *gem install bundler* in a terminal.
* **Slate**

To get slate and create html documentation:
1. Clone the [repository](https://github.com/lord/slate)
2. cd slate
3. Replace [source](source) directory into cloned slate project
4. Run **bundle exec middleman build --clean** - this will create a
build directory with static files. Copy those files to your server www
directory

To test and run locally:
1. bundle install
2. bundle exec middleman server
3. Docs are running at http://localhost:4567