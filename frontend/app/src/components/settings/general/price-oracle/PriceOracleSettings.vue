<script setup lang="ts">
import SettingCategory from '@/components/settings/SettingCategory.vue';
import PriceOracleOrder from '@/components/settings/general/price-oracle/PriceOracleOrder.vue';
import PriceOraclePenalty from '@/components/settings/general/price-oracle/PriceOraclePenalty.vue';

const { t } = useI18n();
</script>

<template>
  <setting-category>
    <template #title>
      {{ t('price_oracle_settings.title') }}
    </template>
    <template #subtitle>
      {{ t('price_oracle_settings.subtitle') }}
    </template>

    <price-oracle-order />
    <price-oracle-penalty />
  </setting-category>
</template>
