# GitHub 업로드 방법

## 제일 쉬운 방법

압축을 푼 폴더에서 `PUSH_TO_GITHUB.bat`를 실행합니다. Git for Windows와 GitHub 인증이 되어 있으면 기존 저장소를 임시 폴더에 clone하고, 전체 프로젝트 트리를 복사한 뒤 `node scripts/verify-repository.mjs` 검사 후 commit/push합니다. 강제 push는 사용하지 않습니다.


GitHub 웹의 "Upload files"로 루트 파일만 올리지 마세요. 이 프로젝트는 `src/`, `tests/`, `docs/`, `scripts/`, `java-sidecar/`, `.github/` 전체가 필요합니다.

## 가장 안전한 방법 (기존 저장소 유지)

```powershell
git clone https://github.com/chobo-coder11/soop-unified-core-v2.git
cd soop-unified-core-v2
```

그 다음 이 ZIP의 **내용물 전체**를 clone한 폴더 안에 복사/덮어쓰기합니다. ZIP 바깥의 상위 폴더 자체를 복사하는 게 아니라 `src`, `tests`, `docs` 등이 저장소 루트에 보이게 복사합니다.

그 후:

```powershell
git add .
git status
git commit -m "Restore full source and add CI safeguards"
git push origin main
```

## 업로드 전 검사

Node.js 20+가 있으면:

```powershell
node scripts/verify-repository.mjs
```

`Repository integrity check passed`가 나와야 합니다.

GitHub에 push 후 Actions 탭에서 `CI`가 실행되고 다음이 모두 성공해야 정상입니다.

- repository-integrity
- node-core
- docker-build

실제 SOOP 네트워크 연결 확인은 Actions의 `SOOP Smoke Test`를 수동 실행해 테스트할 스트리머 ID를 입력합니다.
