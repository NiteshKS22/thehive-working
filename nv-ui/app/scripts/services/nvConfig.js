'use strict';

angular.module('thehive').factory('NvConfig', function() {
  // Configuration for Phase E6.1 UI Strangler
  return {
    MASTER_WRITE_TARGET: window.UI_MASTER_WRITE_TARGET || 'V4',
    useNvQueryReads: window.UI_USE_V5_QUERY_READS === 'true' || false,
    nvBaseUrl: window.UI_V5_QUERY_BASE_URL || '/api/v5',
    fallbackToV4: window.UI_V5_FALLBACK_TO_V4 !== 'false', // Default true
    timeoutMs: parseInt(window.UI_V5_QUERY_TIMEOUT_MS) || 3000
  };
});
