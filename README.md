# Genevieve

Genevieve client: using GenNotes, report ClinVar for individual genomes &amp;
add consensus notes.

## Intended to be reusable

Genevieve processes full genome data to produce reports &ndash; because this
data is potentially private and sensitive, we'd like to enable others to
install personal copies of this web app.

## Examples

**Note: Genevieve is under active development! This isn't the final feature set, it's progress we've made so far.**

- [Genome report screenshot](https://cloud.githubusercontent.com/assets/82631/8336384/13b34ae4-1a72-11e5-8e84-bc47a62ca060.png) - most data in this report was retrieved from GenNotes and loaded via a Javascript

## Local installation/development set-up

*Improvements to these instructions encouraged!*

* **Clone the repository**
  * `git clone https://github.com/PersonalGenomesOrg/genevieve`
* **Using pip and virtualenv, install required packages in a virtualenv**
  * If pip + virtualenv are new to you, check out OpenHatch's [pip and virtualenv](https://openhatch.org/missions/pipvirtualenv) mission (this has instructions and/or links to guides for Debian/Ubuntu, Fedora, and Mac OS X).
  * Make a virtual environment, e.g. `mkvirtualenv genevieve`
  * Install packages: `pip install -r requirements.txt`
  * Later steps which need to be done in this virtual environment will be marked with **[in virtualenv]**
* **Copy `env.example` to `.env`** (note the leading dot!)
  * Set your `SECRET_KEY` with a random string.
  * Set `SUPPORT_EMAIL`. (Used to log in to UCSC's FTP site, and may be used in other contexts.)
  * Set up email. The easiest for development purposes is probably: `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`
* **Install RabbitMQ for messaging**
  * In Debian/Ubuntu:
    * `sudo apt-get install rabbitmq-server`
    * Ubuntu should automatically start the server, but in case that doesn't happen: You can stop the server with `sudo rabbitmqctl stop` and start it running in the background with `sudo rabbitmq-server --detached`.
* **[in virtualenv] Initialize the database:** `python manage.py migrate`
* **[in virtualenv] Run celery:** In one window, run celery (used for genome processing): `celery -A genevieve_client worker -l info`
* **[in virtualenv] Run the web server:** In another window, run: `python manage.py runserver`
* You can now load Genevieve in your web browser by visiting `http://localhost:8000/`
