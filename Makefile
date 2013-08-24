test:
	@python setup.py test

coverage:
	@which coverage 2>&1 >/dev/null || python setup.py testing
	@coverage run setup.py test

report: coverage
	@coverage report docserver.py

report-html: coverage
	@coverage html docserver.py

clean:
	@python setup.py clean
	@rm -rf htmlcov dist *.egg-info
	@find . -name \*.pyc -delete

.PHONY: test coverage report report-html clean
