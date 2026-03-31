# onTong 인증 추상화 레이어 가이드

## 작성일: 2026-03-26
## 목적: 사내 시스템 도입 시 인증 교체를 위한 아키텍처 가이드

---

## 1. 개요

onTong은 현재 인증 없이 동작하지만, 사내 시스템에 도입할 때를 대비해 **인증 추상화 레이어**를 설계했다.
어떤 인증 방식(SSO, LDAP, OIDC, SAML, JWT, API Key 등)이든 **Provider만 교체**하면 전체 시스템이 동작하도록 구성했다.

### 설계 원칙

| 원칙 | 설명 |
|------|------|
| **Provider Pattern** | 인증 로직을 인터페이스 뒤에 캡슐화, 구현체만 교체 |
| **단일 User 모델** | Backend/Frontend 모두 동일한 User 구조 사용 |
| **Router-level 보호** | 개별 엔드포인트가 아닌 라우터 단위로 인증 적용 |
| **Zero-change 배포** | 현재 NoOp provider로 기존 동작에 영향 없음 |

---

## 2. 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                               │
│                                                               │
│   Providers.tsx ─── AuthContextProvider ─── useAuth()         │
│        │                    │                   │             │
│   DevAuthProvider     AuthContext          useAuthFetch()     │
│   (또는 SSOProvider)   (user state)       (auto headers)     │
│                                                               │
├──────────────────────── HTTP ────────────────────────────────┤
│                                                               │
│                        Backend                                │
│                                                               │
│   main.py ─── create_auth_provider() ─── init_auth()         │
│                       │                       │               │
│              NoOpAuthProvider          get_current_user       │
│              (또는 OIDCProvider)    (FastAPI Depends, 전 라우터) │
│                       │                                       │
│                  AuthProvider ABC                              │
│                  ├── authenticate(request) → User             │
│                  ├── on_startup()                             │
│                  └── on_shutdown()                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Backend 구조

### 3.1 파일 구조

```
backend/core/auth/
├── __init__.py          # 공개 API (User, AuthProvider, get_current_user)
├── models.py            # User 모델
├── base.py              # AuthProvider 추상 클래스
├── noop_provider.py     # 개발용 NoOp 구현
├── factory.py           # AUTH_PROVIDER 설정 → 인스턴스 생성
└── deps.py              # FastAPI dependency (get_current_user)
```

### 3.2 User 모델 (`models.py`)

```python
class User(BaseModel):
    id: str           # 고유 식별자 (사번, UUID 등)
    name: str         # 표시 이름
    email: str = ""   # 이메일
    roles: list[str] = []  # 역할 목록 (admin, editor, viewer 등)
```

### 3.3 AuthProvider 인터페이스 (`base.py`)

```python
class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, request: Request) -> User:
        """HTTP 요청에서 인증 정보를 추출하고 User를 반환.
        실패 시 HTTPException(401) 발생."""

    @abstractmethod
    async def on_startup(self) -> None:
        """앱 시작 시 초기화 (JWKS 가져오기, LDAP 연결 등)"""

    @abstractmethod
    async def on_shutdown(self) -> None:
        """앱 종료 시 정리"""
```

### 3.4 인증 적용 방식

모든 API 라우터에 **router-level dependency**로 적용:

```python
from backend.core.auth import get_current_user

router = APIRouter(
    prefix="/api/wiki",
    tags=["wiki"],
    dependencies=[Depends(get_current_user)]  # ← 이 한 줄로 전체 보호
)
```

적용된 라우터:
- `/api/wiki/*` — Wiki CRUD
- `/api/agent/*` — AI 채팅
- `/api/search/*` — 검색
- `/api/approval/*` — 승인/거절
- `/api/files/*` — 파일 업로드/다운로드
- `/api/metadata/*` — 메타데이터

### 3.5 설정

`.env` 파일에서 provider 선택:

```env
AUTH_PROVIDER=noop       # 개발/데모 (기본값)
# AUTH_PROVIDER=oidc     # 사내 SSO 도입 시
# AUTH_PROVIDER=ldap     # LDAP 인증 시
```

---

## 4. Frontend 구조

### 4.1 파일 구조

```
frontend/src/lib/auth/
├── index.ts             # 공개 API
├── types.ts             # User, AuthProvider, AuthState 타입
├── AuthContext.tsx       # React Context + useAuth hook
├── dev-provider.ts      # 개발용 DevAuthProvider
└── fetch.ts             # useAuthFetch — auth 헤더 자동 주입
```

### 4.2 AuthProvider 인터페이스 (`types.ts`)

```typescript
interface AuthProvider {
  init(): Promise<User | null>;              // 초기화 (토큰 확인 등)
  login(): Promise<User>;                    // 로그인
  logout(): Promise<void>;                   // 로그아웃
  getAuthHeaders(): Promise<Record<string, string>>;  // API 헤더
}
```

### 4.3 사용법

```typescript
// 컴포넌트에서 현재 유저 정보 접근
import { useAuth } from "@/lib/auth";

function MyComponent() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  // ...
}
```

```typescript
// 인증 헤더가 자동으로 붙는 fetch
import { useAuthFetch } from "@/lib/auth";

function MyComponent() {
  const { authFetch } = useAuthFetch();
  const res = await authFetch("/api/wiki/tree");  // 헤더 자동 주입
}
```

### 4.4 Provider 교체 포인트

`frontend/src/components/Providers.tsx`:

```typescript
export function Providers({ children }: { children: ReactNode }) {
  // 여기서 Provider만 교체하면 됨
  const authProvider = useMemo(() => new DevAuthProvider(), []);
  // → new SSOAuthProvider({ clientId: "...", redirectUri: "..." })

  return (
    <AuthContextProvider provider={authProvider}>
      {children}
    </AuthContextProvider>
  );
}
```

---

## 5. 새 인증 Provider 추가 가이드

### 5.1 예시: OIDC (사내 SSO) 추가

**Backend** — `backend/core/auth/oidc_provider.py`:

```python
class OIDCAuthProvider(AuthProvider):
    def __init__(self, issuer_url: str, client_id: str):
        self.issuer_url = issuer_url
        self.client_id = client_id
        self.jwks = None

    async def on_startup(self) -> None:
        # OIDC Discovery에서 JWKS 가져오기
        self.jwks = await fetch_jwks(self.issuer_url)

    async def authenticate(self, request: Request) -> User:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            raise HTTPException(401, "Missing token")
        claims = verify_jwt(token, self.jwks, self.client_id)
        return User(
            id=claims["sub"],
            name=claims["name"],
            email=claims["email"],
            roles=claims.get("roles", []),
        )

    async def on_shutdown(self) -> None:
        pass
```

`factory.py`에 등록:

```python
def create_auth_provider(provider_name: str) -> AuthProvider:
    if provider_name == "noop":
        from backend.core.auth.noop_provider import NoOpAuthProvider
        return NoOpAuthProvider()
    elif provider_name == "oidc":
        from backend.core.auth.oidc_provider import OIDCAuthProvider
        return OIDCAuthProvider(
            issuer_url=settings.oidc_issuer_url,
            client_id=settings.oidc_client_id,
        )
```

**Frontend** — `lib/auth/sso-provider.ts`:

```typescript
export class SSOAuthProvider implements AuthProvider {
  private token: string | null = null;

  async init(): Promise<User | null> {
    this.token = localStorage.getItem("sso_token");
    if (!this.token) return null;
    return await this.fetchUserInfo();
  }

  async login(): Promise<User> {
    // SSO 리다이렉트 또는 팝업
    window.location.href = "/auth/sso/login";
    return Promise.reject(); // 리다이렉트되므로 도달하지 않음
  }

  async logout(): Promise<void> {
    localStorage.removeItem("sso_token");
    window.location.href = "/auth/sso/logout";
  }

  async getAuthHeaders(): Promise<Record<string, string>> {
    return this.token ? { Authorization: `Bearer ${this.token}` } : {};
  }
}
```

### 5.2 체크리스트: 새 Provider 추가 시

| # | 항목 | 파일 |
|---|------|------|
| 1 | `AuthProvider` ABC 구현 (Backend) | `backend/core/auth/{name}_provider.py` |
| 2 | `factory.py`에 elif 분기 추가 | `backend/core/auth/factory.py` |
| 3 | `config.py`에 필요한 설정 추가 | `backend/core/config.py` |
| 4 | `.env`에 `AUTH_PROVIDER={name}` + 관련 설정 | `.env` |
| 5 | `AuthProvider` 인터페이스 구현 (Frontend) | `frontend/src/lib/auth/{name}-provider.ts` |
| 6 | `Providers.tsx`에서 provider 교체 | `frontend/src/components/Providers.tsx` |
| 7 | (선택) 로그인 UI 컴포넌트 추가 | `frontend/src/components/LoginPage.tsx` |

---

## 6. 현재 상태 vs 도입 후 비교

| 항목 | 현재 (개발/데모) | 도입 후 (사내 시스템) |
|------|-----------------|---------------------|
| Backend Provider | `NoOpAuthProvider` | `OIDCAuthProvider` 등 |
| Frontend Provider | `DevAuthProvider` | `SSOAuthProvider` 등 |
| 로그인 UI | 없음 (항상 인증됨) | 로그인 페이지 or SSO 리다이렉트 |
| API 헤더 | 없음 | `Authorization: Bearer <token>` |
| User 정보 | 고정 "개발자" | 실제 사번/이름/이메일 |
| `.env` 설정 | `AUTH_PROVIDER=noop` | `AUTH_PROVIDER=oidc` + OIDC 설정들 |

---

## 7. 확장 가능성

- **RBAC (역할 기반 접근 제어)**: `User.roles`를 활용하여 엔드포인트별 권한 체크 가능
- **감사 로그**: `get_current_user`에서 반환된 User를 활용해 누가 무엇을 했는지 추적 가능
- **멀티테넌시**: User 모델에 `tenant_id` 추가로 조직별 데이터 분리 가능
- **문서 작성자 자동 기록**: Wiki 저장 시 `metadata.author`를 현재 로그인 유저로 자동 설정 가능
