coverage:
	@coverage run setup.py test

report: coverage
	@coverage report docserver.py

report-html: coverage
	@coverage html docserver.py

clean:
	@rm -rf htmlcov dist *.egg-info __pycache__ .tox *.egg .coverage
	@find . -name \*.pyc -delete

.PHONY: coverage report report-html clean
