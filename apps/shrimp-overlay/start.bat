@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 새우 채팅마을
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js가 설치되어 있지 않습니다.
  echo Node.js 24 설치 후 이 파일을 다시 실행해 주세요.
  echo https://nodejs.org/
  pause
  exit /b 1
)
node launch.mjs
if errorlevel 1 pause
