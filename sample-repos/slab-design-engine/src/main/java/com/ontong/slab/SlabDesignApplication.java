package com.ontong.slab;

import com.ontong.slab.config.EquipmentProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

/**
 * Slab 설계 엔진 부팅 엔트리.
 *
 * 공정계획 단계에서 수주 사양(OrderSpec)을 받아 설비 제약을 만족하는
 * 최대 중량의 직육면체 Slab 치수를 반환한다.
 */
@SpringBootApplication
@EnableConfigurationProperties(EquipmentProperties.class)
public class SlabDesignApplication {

    public static void main(String[] args) {
        SpringApplication.run(SlabDesignApplication.class, args);
    }
}
