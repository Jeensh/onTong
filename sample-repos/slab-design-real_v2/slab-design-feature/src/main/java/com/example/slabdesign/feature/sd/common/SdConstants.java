package com.example.slabdesign.feature.sd.common;

/**
 * Slab design algorithm constants extracted from v1's drama-DNA magic numbers.
 * Numerical values are identical to v1 to preserve algorithm output.
 */
public final class SdConstants {

    /** Default cumulative productivity multiplier when productivity_std lookup misses. */
    public static final double DEFAULT_PRODUCTIVITY = 0.95;

    /** Default specific gravity (강종별 분기 자리만 마련, 현재 상수). */
    public static final double DEFAULT_SPECIFIC_GRAVITY = 7.82;

    /** Sentinel "no upper bound" value used in width / length / weight ranges. */
    public static final double NO_UPPER_BOUND = 999999.999;

    /** Length of confirmedPlantCd in characters; one position per process. */
    public static final int CONFIRMED_PLANT_CD_LENGTH = 8;

    /** Inactive process marker in confirmedPlantCd. */
    public static final char INACTIVE_PROCESS = ' ';

    /** SLAB_RESULT.SLAB_NO is a 12-digit zero-padded string. */
    public static final int SLAB_NO_DIGITS = 12;

    /** 8 production processes in confirmedPlantCd position order. */
    public static final String[] PROC_CODES = {
        "SM", "HR", "HRF", "CR", "ANL1", "ANL2", "GAL", "CRF"
    };

    private SdConstants() {}
}
