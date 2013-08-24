test:
	@python setup.py test

coverage:
	@which coverage 2>&1 >/dev/null || python setup.py testing
	@coverage run setup.py test
	@coverage report docserver.py

coverage-html: coverage
	@coverage html docserver.py
	@xdg-open htmlcov/index.html

clean:
	@python setup.py clean
	@rm -rf htmlcov dist *.egg-info
	@find . -name \*.pyc -delete

.PHONY: test coverage coverage-html clean
