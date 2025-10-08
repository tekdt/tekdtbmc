cd "%~dp0"

:Install_DRV
rem install your driver here pnputil -i -a
CALL "installdrv.cmd"
rem pnputil -i -a xxxxComponentxxx.inf
rem after driver install
popd

:END