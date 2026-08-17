@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "REPO=https://github.com/chobo-coder11/soop-unified-core-v2.git"
set "ROOT=%~dp0"
set "WORK=%TEMP%\soop-unified-core-upload-%RANDOM%-%RANDOM%"

echo [1/5] Git 확인...
where git >nul 2>nul || (
  echo ERROR: Git이 설치되어 있지 않습니다.
  echo https://git-scm.com/ 에서 Git for Windows를 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

echo [2/5] 저장소 clone...
git clone "%REPO%" "%WORK%" || (
  echo ERROR: GitHub 저장소 clone 실패. GitHub 인증 상태를 확인하세요.
  pause
  exit /b 1
)

echo [3/5] 전체 프로젝트 파일 동기화...
robocopy "%ROOT%" "%WORK%" /E /R:1 /W:1 /XD ".git" "node_modules" "dist" /XF ".env" "*.log" >nul
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  echo ERROR: 파일 복사 실패 ^(robocopy code %RC%^).
  pause
  exit /b %RC%
)

pushd "%WORK%"

echo [4/5] 저장소 무결성 검사...
node scripts\verify-repository.mjs || (
  echo ERROR: src/tests/docs/java-sidecar/.github 중 필수 파일이 누락되어 push를 중단합니다.
  popd
  pause
  exit /b 1
)

git add -A
for /f %%i in ('git status --porcelain ^| find /c /v ""') do set "CHANGES=%%i"
if "!CHANGES!"=="0" (
  echo 변경사항이 없습니다. 이미 최신 상태입니다.
  popd
  rmdir /s /q "%WORK%" 2>nul
  pause
  exit /b 0
)

echo [5/5] commit + push...
git commit -m "Restore full source and add CI safeguards" || (
  echo ERROR: commit 실패. git user.name/user.email 설정을 확인하세요.
  popd
  pause
  exit /b 1
)
git push origin main || (
  echo ERROR: push 실패. GitHub 로그인/권한을 확인하세요.
  echo 작업 폴더: %WORK%
  popd
  pause
  exit /b 1
)

popd
rmdir /s /q "%WORK%" 2>nul

echo.
echo SUCCESS: 전체 소스가 GitHub main 브랜치에 push 되었습니다.
echo GitHub Actions의 CI 결과를 확인하세요.
pause
