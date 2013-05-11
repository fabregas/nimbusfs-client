
VER=`git describe --always --tag`
TEST_RUNNER:=./tests/runTests

export PYTHONPATH=./

compile:
	@echo 'This method is not implemented' 

clean:
	@echo "rm -rf ./dist"; rm -rf ./dist
	@echo "rm -rf ./build"; rm -rf ./build


test:
	@$(TEST_RUNNER)

generate_forms:
	python generate_forms.py id_client/gui/forms/

build_mac:
	python setup_mac.py py2app
	hdiutil create -srcfolder dist/Idepositbox.app dist/iDepositBox-${VER}.dmg
