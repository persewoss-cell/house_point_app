# 🏠 우리집 포인트 통장 🪙 (v2)

Streamlit으로 만들었던 우리집 포인트 통장을 **GitHub Pages 웹사이트**로 옮긴 버전입니다.
서버 없이 브라우저가 **기존 Firebase(Firestore) 데이터를 그대로** 읽고 씁니다.

- 화면: React (학급 경제 시스템 v2 디자인)
- 데이터: 기존 Firebase Firestore (컬렉션·필드 구조 그대로, 옮기기 작업 없음)
- 배포: GitHub Actions → GitHub Pages (코드를 올리면 자동으로 다시 배포)

---

## 🚀 처음 한 번만 하는 설정

### 1) Firebase: 익명 로그인 켜기
1. [Firebase 콘솔](https://console.firebase.google.com) → 기존 프로젝트 선택
2. 왼쪽 **빌드 → Authentication** → (처음이면 **시작하기**) → **로그인 방법** 탭
3. **익명** → 사용 설정 → 저장

### 2) Firebase: 웹 앱 설정값 넣기
1. Firebase 콘솔 → 톱니바퀴 **프로젝트 설정** → **일반** 탭 → 아래 **내 앱**
2. 웹 앱(`</>`)이 없으면 **앱 추가 → 웹** → 닉네임 아무거나(예: house-web) → 등록 (Firebase 호스팅은 체크하지 않음)
3. **SDK 설정 및 구성 → 구성**에 나오는 `apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId` 값을
   이 저장소의 `src/firebaseConfig.js` 에 붙여 넣고 저장(커밋)
   > 이 값들은 원래 공개되는 값이라 깃허브에 올려도 괜찮아요. 데이터는 아래 보안 규칙이 지켜요.

### 3) Firebase: 보안 규칙 바꾸기
1. Firebase 콘솔 → **Firestore Database → 규칙** 탭
2. 이 저장소의 `firestore.rules` 내용을 그대로 붙여 넣고 **게시**
   - 앱에 들어온 사람(익명 로그인)만 데이터를 읽고 쓸 수 있어요.
   - 기존 Streamlit 앱은 관리자 키를 쓰기 때문에 이 규칙과 상관없이 계속 동작해요.

### 4) GitHub Pages 켜기
1. GitHub 저장소 → **Settings → Pages**
2. **Build and deployment → Source** 를 **GitHub Actions** 로 선택
3. (작업 브랜치에서 미리 보고 싶다면) **Settings → Environments → github-pages → Deployment branches and tags** 에 `claude/*` 추가
4. **Actions** 탭에서 배포가 끝나면 `https://persewoss-cell.github.io/house_point_app/` 에서 열려요.

### 5) 관리자 비밀번호 정하기 (처음 한 번)
1. 사이트에서 이름에 `관리자` 를 넣고 로그인을 누르면 **관리자 비밀번호 설정 화면**이 나와요.
2. 새 관리자 비밀번호를 정해요. (4자 이상, 영문+숫자로 길게 정할수록 안전)
3. 이후 변경은 관리자 화면 오른쪽 위 **🔐 계정관리** 팝업 맨 아래에서 할 수 있어요.

> ⚠️ 배포 직후 바로 관리자 비밀번호를 정해 주세요. (정하기 전에는 사이트 주소를 아는 누구나 처음 설정을 할 수 있어요)

---

## 🔒 보안에 대해 (가족용 기준)
- 관리자 비밀번호는 코드에 없고, Firestore `config/admin_auth` 에 **암호화(해시)된 값**만 저장돼요.
- 다만 서버가 없는 구조라서, 개발자도구를 다룰 줄 아는 사람은 Firestore 데이터를 직접 볼 수 있어요.
  가족끼리 쓰는 용도로는 충분하지만, 중요한 비밀번호(은행 비밀번호 등)를 재사용하지 마세요.

---

## 🧑‍💻 직접 실행해 보기 (선택)
```bash
npm install
npm run dev
```

## 📁 폴더 구조
```
src/firebaseConfig.js   Firebase 웹 앱 설정값 (2단계에서 입력)
src/backend/            데이터 처리 (기존 app.py의 api_* 함수들 → Firestore 직접 사용)
  core.js               잔액·거래·요약 공통 계산
  actions/*.js          메뉴별 기능
src/App.jsx             로그인 · 메인 메뉴(탭) 구성
src/tabs/*.jsx          메뉴 화면
src/components/         버튼·입력칸·표 등 공용 부품
firestore.rules         Firestore 보안 규칙 (3단계에서 콘솔에 붙여 넣기)
.github/workflows/      자동 배포 설정
```

## 🗺️ 옮기기 진행 상황
- ✅ 1단계: 로그인 · 메뉴 · 💰입금/출금(개인/전체/템플릿/되돌리기) · 📝 통장/거래 · 🔎 개별조회 · 계정관리
- ✅ 2단계: 🏦 적금 · 📈 투자 · 💼 직업/월급 (+ 적금 만기·월급 자동지급)
- ⬜ 3단계: 🏷️ 경매 · 🍀 복권 · 🎯 목표
