# Popcat Trash for Windows

Mac의 [cat-trash](https://github.com/Gojaehyeon/cat-trash) 컨셉을 Windows에 이식한 보조 휴지통 위젯.
파일을 끌어다 고양이에 떨어뜨리면 고양이가 입을 벌리고 닫으며 파일을 휴지통으로 보낸다.

## 동작

- 평소: 입 다문 고양이 (대기)
- 파일 드래그가 위젯 위로 올라옴: 입 벌림 (받을 준비)
- 그냥 빠져나감: 즉시 입 다묾
- 실제 드롭됨: 입 벌린 채 휴지통으로 이동 → 0.4초 후 입 다묾
- 시작 시 z-order 맨 아래로 이동 → 다른 창들 뒤에 위치
- 시스템 트레이 아이콘 좌클릭: 위젯을 5초간 모든 창 위로 올림

## 설치 (직원용 - 가장 간단)

1. Releases에서 `CatTrash.exe` 다운로드
2. 원하는 폴더에 저장 후 더블클릭
3. Windows SmartScreen 경고가 뜨면 `추가 정보` → `실행`
4. 화면 우하단에 위젯 등장. 작업표시줄 트레이에도 고양이 아이콘 추가됨

설치 과정, 관리자 권한, 레지스트리 수정, Python 설치 일절 없음. 단일 .exe로 끝.

## 사용

| 동작 | 결과 |
|---|---|
| 파일 드래그 → 위젯에 드롭 | 휴지통으로 이동 |
| 트레이 아이콘 좌클릭 | 위젯 5초간 위로 올라옴 |
| 트레이 아이콘 우클릭 | 메뉴 (휴지통 비우기 / 종료 등) |
| 위젯 좌클릭 + 드래그 | 위치 이동 |
| 위젯 우클릭 | 메뉴 (잠금 / 비우기 / 종료) |

## 자동 실행 등록

1. `Win + R` → `shell:startup` 입력 → 시작프로그램 폴더 열림
2. `CatTrash.exe`의 바로가기 만들어 그 폴더에 넣기

## 소스에서 직접 실행 (개발자/수정용)

### 필요 사항

- Python 3.10+ ([https://www.python.org/downloads/](https://www.python.org/downloads/))
- 설치 시 `Add Python to PATH` 체크 필수

### 실행

```cmd
run.bat
```

처음 실행 시 PySide6와 의존 패키지가 자동 설치된다 (1~2분).

### 진단 (오류 발생 시)

```cmd
debug_run.bat
```

각 단계 결과를 콘솔창에서 확인 가능.

## 단일 .exe 빌드 (배포용)

```cmd
build_exe.bat
```

1~3분 후 `CatTrash.exe` 생성. 다른 PC에 복사해서 그대로 사용 가능 (Python 미설치 PC에서도 동작).

빌드 환경:
- Windows 10/11
- Python 3.10+
- PyInstaller, PySide6, Pillow (build_exe.bat이 자동 설치)

### 경로 길이 주의

Windows의 `MAX_PATH = 260` 제한 때문에 깊은 경로에서 빌드 시 실패할 수 있다. 짧은 경로(예: `C:\popcat\`)에서 빌드하는 것을 권장.

## 파일 구성

```
popcat/
├── cat_trash_win.py    # 메인 코드 (PySide6 위젯)
├── white_open.png      # 입 벌린 고양이 (호버/드롭 시)
├── white_closed.png    # 입 다문 고양이 (평상시)
├── run.bat             # 평소 실행 (백그라운드)
├── debug_run.bat       # 진단용 실행 (콘솔 표시)
├── build_exe.bat       # 단일 .exe 빌드
├── README.md           # 이 파일
└── .gitignore
```

## 기술 스택

- Python 3.10+
- PySide6 (Qt for Python) - GUI 프레임워크
- ctypes + Windows Shell API (`SHFileOperationW`) - 휴지통 이동
- ctypes + `SetWindowPos(HWND_BOTTOM)` - 바탕화면 레이어 위치
- PyInstaller - 단일 .exe 패키징

## 한계 및 주의사항

- **Windows 전용** — macOS/Linux 미지원
- **MAX_PATH 제한** — 깊은 폴더 경로에서 빌드 시 실패
- **실시간 호버 애니메이션** — Mac Dock과 달리 Windows에는 글로벌 드래그 호버 이벤트가 없음. 위젯 영역 내로 들어와야 입 벌림 반응
- **z-order 고정의 한계** — `SetWindowPos(HWND_BOTTOM)`은 호출 시점에만 z-order를 맨 아래로 보냄. 새 창이 열리면 그 위에 표시되지만, 클릭 시 위로 올라올 수 있음
- **안티바이러스 오탐 가능** — PyInstaller로 빌드된 .exe는 일부 백신이 의심 파일로 표시할 수 있음. 코드 서명 인증서 미적용

## 라이선스

MIT (또는 본인이 선택한 라이선스로 변경)

## 원본 영감

- [Gojaehyeon/cat-trash](https://github.com/Gojaehyeon/cat-trash) — macOS 버전
- Pop Cat 밈 — 위키미디어
