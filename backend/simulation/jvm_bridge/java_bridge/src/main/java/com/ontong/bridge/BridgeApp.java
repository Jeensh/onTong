package com.ontong.bridge;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.kafka.KafkaAutoConfiguration;
import org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration;

/**
 * onTong Java Bridge — Spring Boot CLI.
 *
 * slab-design 의 SdDesigner.design() 만 호출. Oracle/Kafka 의존성은
 * MockConfig 의 @Primary @Bean override 로 swap.
 *
 * scanBasePackages 에 slab-design 의 feature 패키지를 명시적으로 추가하여
 * @Component, @Service, @Repository (mock 인 것 제외) 가 모두 로드되게 함.
 *
 * exclude 로 DB / JPA / Kafka auto-configuration 제거 — 실 connection 시도 차단.
 */
@SpringBootApplication(
    scanBasePackages = {
        "com.ontong.bridge",
        "com.example.slabdesign.feature"
    },
    exclude = {
        DataSourceAutoConfiguration.class,
        HibernateJpaAutoConfiguration.class,
        KafkaAutoConfiguration.class
    }
)
public class BridgeApp {
    public static void main(String[] args) {
        // 로그를 stderr 로 — stdout 은 JSON 응답 전용.
        System.setProperty("logging.pattern.console", "");
        System.setProperty("spring.main.banner-mode", "off");

        SpringApplication app = new SpringApplication(BridgeApp.class);
        app.setLogStartupInfo(false);
        app.run(args);
    }
}
