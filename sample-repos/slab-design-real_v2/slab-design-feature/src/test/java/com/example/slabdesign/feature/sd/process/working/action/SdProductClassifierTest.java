package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.ProductCategory;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdProductClassifier}.
 *
 * 도메인 룰: 품명 앞 2글자 'FS' = PLATE, 그 외 = COIL, NULL/짧은코드 = UNKNOWN.
 */
class SdProductClassifierTest {

    private final SdProductClassifier classifier = new SdProductClassifier();

    @Test
    void coilProduct_returnsCoil() {
        assertThat(classifier.classifyByProductCode("COIL")).isEqualTo(ProductCategory.COIL);
        assertThat(classifier.classifyByProductCode("HR1")).isEqualTo(ProductCategory.COIL);
    }

    @Test
    void fsProduct_returnsPlate() {
        assertThat(classifier.classifyByProductCode("FS01")).isEqualTo(ProductCategory.PLATE);
        assertThat(classifier.classifyByProductCode("fs02")).isEqualTo(ProductCategory.PLATE); // case-insensitive
    }

    @Test
    void nullOrShort_returnsUnknown() {
        assertThat(classifier.classifyByProductCode(null)).isEqualTo(ProductCategory.UNKNOWN);
        assertThat(classifier.classifyByProductCode("F")).isEqualTo(ProductCategory.UNKNOWN);
        assertThat(classifier.classifyByProductCode("")).isEqualTo(ProductCategory.UNKNOWN);
    }

    @Test
    void isDesignableInDemo_onlyForCoil() {
        SDOrderEntity coilOrder = new SDOrderEntity();
        coilOrder.setProductCd("COIL");
        SDOrderEntity plateOrder = new SDOrderEntity();
        plateOrder.setProductCd("FS01");

        assertThat(classifier.isDesignableInDemo(coilOrder)).isTrue();
        assertThat(classifier.isDesignableInDemo(plateOrder)).isFalse();
        assertThat(classifier.isDesignableInDemo(null)).isFalse();
    }
}
