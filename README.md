# 🏠 우리집 포인트 통장 🪙

가족끼리 쓰는 포인트 통장 웹사이트입니다.
👉 **https://persewoss-cell.github.io/house_point_app/**

- 화면: React (학급 경제 시스템 v2 디자인)
- 데이터: Firebase Firestore (예전 Streamlit 앱 데이터 그대로 사용)
- 배포: `main` 브랜치에 코드가 올라가면 GitHub Actions가 자동으로 GitHub Pages에 배포
- 서버 없음: 브라우저가 Firestore에 바로 읽고 씀 (`src/backend`)

---

## 📋 메뉴

| 관리자 | 가족 |
|---|---|
| 💰 입금/출금 (개인·전체·템플릿·엑셀·되돌리기) | 📝 통장/거래 |
| 🔎 개별조회 (요약·통장내역·적금·목표·내역 삭제) | 🏦 적금 (가입·중도해지, 만기 자동 지급) |
| 💼 직업/월급 (공제·지급일·자동/수동 지급·고용/해제·엑셀) | 📈 투자 (투자하기·내 장부) |
| 📈 투자 (주가 변동·그래프·회수 지급·종목 관리) | 🎯 목표 |
| 🏷️ 경매 (개시·마감·장부 반영·낙찰금 반환) | 🏷️ 경매 (입찰) |
| 🍀 복권 (개시·마감·추첨·당첨금 지급·장부) | 🍀 복권 (구매) |

- 관리자 화면 오른쪽 위 **🔐 계정관리**: 가족 계정 생성 / 비밀번호 변경 / 삭제, 관리자 비밀번호 변경
- 가족 화면 위 **🔑 비밀번호 변경**: 본인 비밀번호 변경 (다른 기기는 자동 로그아웃)
- 적금 만기 지급과 월급 자동지급은 누군가 로그인하거나 사이트를 새로고침할 때 자동으로 처리돼요.

---

## ⚙️ 설정 (이미 완료됨 — 새 Firebase 프로젝트로 옮길 때만 다시)

1. **익명 로그인 켜기**: Firebase 콘솔 → Authentication → 로그인 방법 → **익명** 사용 설정
2. **웹 앱 설정값**: Firebase 콘솔 → 프로젝트 설정 → 내 앱(웹 `</>`) → 구성 값을 `src/firebaseConfig.js`에 붙여 넣기
   (공개되는 값이라 깃허브에 올려도 괜찮아요. Streamlit용 `firebase_key.json`은 필요 없고 절대 올리면 안 돼요.)
3. **보안 규칙**: Firestore Database → 규칙 탭에 `firestore.rules` 내용을 붙여 넣고 게시
4. **GitHub Pages**: Settings → Pages → Source를 **GitHub Actions**로
5. **관리자 비밀번호**: 사이트에서 이름 `관리자`로 로그인하면 처음 한 번 설정 화면이 나와요.
   관리자 비밀번호는 Firestore `config/admin_auth`에 암호화(해시)된 값으로만 저장돼요.

> ⚠️ 서버가 없는 구조라 개발자도구를 다룰 줄 아는 사람은 Firestore 데이터를 직접 볼 수 있어요.
> 가족용으로는 충분하지만, 중요한 비밀번호(은행 등)를 재사용하지 마세요.

---

## 🛠️ 문제가 생기면
- **"Firestore 색인(index)이 필요해요"**: 브라우저 F12 → Console에 나온 링크를 눌러 색인을 만들면 돼요.
- **"데이터 접근이 거부됐어요"**: Firestore 보안 규칙(3번)과 익명 로그인(1번)을 확인하세요.
- **사이트가 안 바뀌어요**: GitHub → Actions 탭에서 배포가 초록 ✅인지 확인하세요.

---

## 🧑‍💻 직접 실행해 보기 (선택)
```bash
npm install
npm run dev
```
실제 데이터를 건드리지 않고 시험하려면 Firebase 에뮬레이터를 켠 뒤 `VITE_USE_EMULATOR=1 npm run dev` 로 실행하세요. (`firebase.json`)

## 📁 폴더 구조
```
src/firebaseConfig.js   Firebase 웹 앱 설정값
src/backend/            데이터 처리 (Firestore 직접 사용)
  auth.js               로그인·관리자 비밀번호
  core.js               잔액·거래·요약 공통 계산
  actions/*.js          메뉴별 기능
src/App.jsx             로그인 · 메인 메뉴 구성
src/tabs/*.jsx          메뉴 화면
src/components/         버튼·입력칸·표 등 공용 부품
firestore.rules         Firestore 보안 규칙
.github/workflows/      자동 배포 설정
```
