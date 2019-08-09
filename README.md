# vvWeb

Django web app to run and display results from VariantValidator

## Installation

Download the source files through git

```bash
git clone https://github.com/openvar/vvweb
cd vvweb
```

To run the batch processes, you'll need to install and setup [RabbitMQ](https://www.rabbitmq.com/download.html) and [Celery](http://docs.celeryproject.org/en/latest/index.html).
Note that this isn't necessary if you only wish to run the interactive processes. 

To install the python packages you should first create a python 3.6 virtual environment.

```bash
# if you have conda installed
conda env -f environment.yml
conda activate vvweb

# otherwise
module load python/gcc/3.6.4  # only if on SPECTRE
python -m venv vvweb
source activate vvweb
pip install -r requirements.txt
```

This will likely fail as it won't be able to install VariantValidator>1.0 (hasn't been released yet), 
you should therefore at this point go to the [VV git repo](https://github.com/openvar/variantValidator)
and checkout the `develop_v1` branch. Install and configure that version of VariantValidator within your virtual environment.

```bash
# Should look something like this
cd ../
git clone https://github.com/openvar/variantValidator
cd variantValidator/
git checkout develop_v1
python setup.py install
vv_configure.py  # will allow you to configure database connections etc 
variant_validator.py -v "NM_000088.3:c.589G>T"  # Check it's working
cd ../vvweb/
```

## Django setup

Once everything is installed and you've got a complete virtual environment, you then need to setup django.

First, create a `local_settings.py` file within `VVweb/`. Inside should be all private settings, including a secrete key. It should look something like:

```python
# Note, this key shouldn't be used in any publically accessible version
SECRET_KEY = '+htjqfu=nn$+(vcs8sdx1=^2lprn8pj(s1zs4z4jv$*l%pxs68'

VARSOME_TOKEN = 'NEED_A_TOKEN'
```

To setup and create the database, first create a migration (checks what models need creating) and then migrate it into the database (currently a local sqlite database).

```bash
python manage.py makemigrations
python manage.py migrate
```

Then, you should be able to launch the development server

```bash
python manage.py runserver
```

## Celery and RabbitMQ

To run asynchronous tasks you need celery to talk to the Django app, via a broker (in out case RabbitMQ).
Once RabbitMQ is running it should be connected to port 5672. This can be done by installing RabbitMQ from an RPM, from source or via a docker image.

```bash
# Docker 
docker run -d --hostname my-rabbit --name some-rabbit -p 5672:5672 rabbitmq
```

Once the rabbit service is running, start Celery within the vvweb directory. Note, that you need to be in the 
virtual environment as thats where we installed celery.

```bash
celery -A VVweb worker -l info
```

Celery will then listen for tasks and run them asynchronously.

## Submitting changes

To make a change to vvWeb, first checkout a new branch within git.

```bash
# pull in latest changes
git pull
# -b creates a new branch
git checkout -b new_branch_name
```

Your branch name should be specific to the task you're working on. If you want to work on two or more tasks, each should go in their own branch.

Once you've made a change, commit it into git by selecting the files you want to commit, and then making the commit with a message.
Commits should be atomic, i.e. "of or forming a single irreducible unit or component in a larger system". So as small as possible, but containing all changes
related to that one thing. For example, if we wanted to change the name of the validator we'd make one commit that contains that change in all the relevant files. 
If we spotted a typo at the same time, that would go in a separate commit as it's not part of the validator name change.

```bash
git add file1 file4
git add --patch file2  # this will allow you to add only part of the file
git commit -m "Message describing my change"
```

Once you've made your commits, push them to the remote version on GitHub (called origin)

```bash
git push -u origin new_branch_name
```

Once you've done all the work for that branch/task, and it's been pushed to GitHub, make a Pull Request
online to suggest merging your new branch into master. Assign me as a reviewer so I get emailed about your PR. Once I've merged the change,
I'll delete the new branch.

To then start working on a new task/branch, checkout master, ensure it's up-to-date and then make a new branch.
When you branch it contains all the changes from the branch you're currently on, which is why you want to make sure
that you're starting from the right place.

```bash
git checkout master
git pull
git checkout -b another_new_branch
```

If you're ever unsure about what changes are in your current working directory, or
which branch you're on run `git status`. In fact I run that before, during and after every
add/commit to make sure I've got the right files and am in the right place before committing anything.
