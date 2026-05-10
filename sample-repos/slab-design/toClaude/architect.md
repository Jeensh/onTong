## 기술스택
- 언어 : 자바 21
- 주요 사용 프레임워크
    - Spring
    - Spring Data Jpa
    - Mybatis
    - spring cloud (카프카용)
- 주요 사용 인프라 기술
    - 카프카
    - oracle db
    - Maven (POM.xml)

## 소스 구조
```
slab-design
└─slab-design-boot
│   ├─java
│   │   ├─config  // @Configuration, TypeAdapter 등 스프링, 라이브러리 설정
│   │   └─sample  // config와 동일(테스트용)
│   └─resources  // bootstrap.yml 등 앱 설정
│
├─slab-design-facade
│   └─java
│       ├─task(cd, em..)
│       │   ├─event  // kafka Listener
│       │   └─rest  // @RestController 등 API
│       │      ├─analysis  // 분석 관련 기능 API
│       │      ├─history  // 이력 관리 기능 API
│       │      ├─std    // 기준 관리 기능 API
│       │      └─working  // job 관련 기능 API
│       └─exception  // 에러처리(ex. ExceptionHandler)
│
├─slab-design-feature
│   └─java
│       └─task(cd, em..)
│           ├─designer // service 흐름 제어(단위 job 수행)  
│           ├─driver   // designer 흐름 제어(복합 job 수행)
│           └─process
│              └─기능분류(analysis, history, std, working)
│                 ├─action  // 기본 비즈니스 로직 담당
│                 ├─service  // action 흐름 제어(action 상위 모듈)
│                 └─wrapper  // req, res DTO
│
└─slab-design-store
    └─java
        └─task(cd, em..)
            └─기능분류(analysis, history, std, working)
               ├─domain  
               │  ├─entity    // Domain Entity(JPO는 feature계층에서 사용 불가)
               │  └─logic    // Domain Entity <-> JPO 변환 및 검증(xxxStore 상위 모듈)
               └─oracle
                  ├─jpo      // @Entity, @IdClass .. 
                  └─repository  // JpaRepository
```