
VER=`git describe --always --tag`
M=`uname -m`
TEST_RUNNER:=./tests/runTests

export PYTHONPATH=./:./third-party

update_version:
	echo "VERSION='${VER}'" > id_client/version.py

compile:
	@echo 'This method is not implemented' 

clean:
	@echo "rm -rf ./dist"; rm -rf ./dist
	@echo "rm -rf ./build"; rm -rf ./build


test: update_version
	@$(TEST_RUNNER)

test_all:
	@$(TEST_RUNNER) with_web

make_test_suid_app:
	rm -rf ./bin/rbd_manage
	gcc -o ./bin/rbd_manage suid_disk_manage.c
	sudo chown root:root ./bin/rbd_manage
	sudo chmod 4755 ./bin/rbd_manage

make_suid_app:
	mkdir -p ./bin/${ARCH}
	rm -rf ./bin/${ARCH}/rbd_manage
	${CC} ${CFLAGS} -o ./bin/${ARCH}/rbd_manage suid_disk_manage.c
	strip ./bin/${ARCH}/rbd_manage

generate_forms:
	python generate_forms.py id_client/gui/forms/

build_mac:
	python setup_mac.py py2app
	hdiutil create -srcfolder dist/Idepositbox.app dist/iDepositBox-${VER}.dmg
