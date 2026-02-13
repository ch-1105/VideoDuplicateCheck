@echo off
setlocal

if exist build rmdir /s /q build
if exist dist\onedir rmdir /s /q dist\onedir
if exist dist\onefile rmdir /s /q dist\onefile
if exist VideoDuplicateCheck.spec del /q VideoDuplicateCheck.spec

echo Build artifacts removed.
exit /b 0
