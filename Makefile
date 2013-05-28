
VER=`git describe --always --tag`
M=`uname -m`
TEST_RUNNER:=./tests/runTests

export PYTHONPATH=./:./third-party

compile:
	@echo 'This method is not implemented' 

clean:
	@echo "rm -rf ./dist"; rm -rf ./dist
	@echo "rm -rf ./build"; rm -rf ./build


test:
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
	rm -rf ./bin/${ARCH}/webdav_mount
	sed -e 's/{RELPATH}/id_client\/security\/mng_block_device.py/g' suid_template.c > suid_disk_manage.c
	sed -e 's/{RELPATH}/id_client\/webdav_mounter.py/g' suid_template.c > suid_mounter.c
	${CC} ${CFLAGS} -o ./bin/${ARCH}/rbd_manage suid_disk_manage.c
	${CC} ${CFLAGS} -o ./bin/${ARCH}/webdav_mount suid_mounter.c
	strip ./bin/${ARCH}/rbd_manage
	strip ./bin/${ARCH}/webdav_mount
	rm suid_mounter.c
	rm suid_disk_manage.c

generate_forms:
	python generate_forms.py id_client/gui/forms/

build_mac:
	python setup_mac.py py2app
	hdiutil create -srcfolder dist/Idepositbox.app dist/iDepositBox-${VER}.dmg

install_linux_gui_icon:
	xdg-desktop-icon install --novendor contrib/idepositbox.desktop
	xdg-desktop-menu install --novendor contrib/idepositbox.desktop
