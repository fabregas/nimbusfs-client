
VER=`git describe --always --tag`
M=`uname -m`
TEST_RUNNER:=./tests/runTests

export PYTHONPATH=./

compile:
	@echo 'This method is not implemented' 

clean:
	@echo "rm -rf ./dist"; rm -rf ./dist
	@echo "rm -rf ./build"; rm -rf ./build


test:
	@$(TEST_RUNNER)

make_suid_app:
	rm -rf ./bin/$M
	mkdir ./bin/$M
	gcc -o ./bin/$M/rbd_manage suid_disk_manage.c
	sudo chown root:root ./bin/$M/rbd_manage
	sudo chmod 4755 ./bin/$M/rbd_manage

generate_forms:
	python generate_forms.py id_client/gui/forms/

build_mac:
	python setup_mac.py py2app
	hdiutil create -srcfolder dist/Idepositbox.app dist/iDepositBox-${VER}.dmg
