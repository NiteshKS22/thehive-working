(function () {
    'use strict';

    /**
     * nvSocketSrv — Vyuha-Stream WebSocket Client
     *
     * Maintains a persistent, authenticated WebSocket connection to nv-socket-service.
     * Broadcasts Angular events when messages arrive so controllers can react.
     *
     * GUARDRAILS IMPLEMENTED:
     *  - TENANT_ISOLATION  : token contains tenant_id; server enforces matching path
     *  - GRACEFUL_DEGRADE  : on disconnect, switches to 30s polling + shows offline badge
     *  - MINIMAL_PAYLOAD   : receives {type, id, tenant_id, timestamp}; UI fetches details
     */
    angular.module('theHiveServices').factory('NvSocketSrv', function (
        $rootScope, $interval, $timeout, NvConfig, AuthenticationSrv, NotificationSrv
    ) {

        var SOCKET_URL = NvConfig.nvSocketUrl || (window.location.origin.replace(/^http/, 'ws') + '/ws');
        var POLL_INTERVAL = 30000;   // 30s fallback polling
        var RECONNECT_STEPS = [1000, 2000, 4000, 8000, 30000]; // exponential backoff caps
        var HIGH_SEV_MIN = 3;        // Severity >= 3 triggers toast

        var svc = {
            connected: false,
            offline: false,
            presence: {},            // {case_id: [user_id, ...]}
        };

        var _ws = null;
        var _pollTimer = null;
        var _reconnectTimer = null;
        var _reconnectStep = 0;
        var _currentCaseId = null;

        // ── Token helper ─────────────────────────────────────────────────────
        function _getToken() {
            return AuthenticationSrv.currentUser && AuthenticationSrv.currentUser.token;
        }

        function _getTenantId() {
            return AuthenticationSrv.currentUser && AuthenticationSrv.currentUser.organisation;
        }

        // ── Dispatch incoming events ─────────────────────────────────────────
        function _dispatch(msg) {
            switch (msg.type) {
                case 'PING':
                    if (_ws && _ws.readyState === WebSocket.OPEN) {
                        _ws.send(JSON.stringify({ type: 'PONG' }));
                    }
                    break;

                case 'NEW_ALERT':
                    $rootScope.$broadcast('nv:alert:new', { id: msg.id });
                    // Toast on high-severity — UI fetches severity via nv-query after getting id
                    NotificationSrv.log(
                        '🔴 New Alert',
                        'A new alert has arrived. <a href="/#!/alerts/' + msg.id + '">View</a>',
                        'warning'
                    );
                    break;

                case 'CASE_UPDATED':
                    $rootScope.$broadcast('nv:case:updated', { id: msg.id });
                    break;

                case 'ARTIFACT_UPLOADED':
                    $rootScope.$broadcast('nv:evidence:refresh', { id: msg.id });
                    break;

                case 'ANALYST_PRESENCE':
                    svc.presence[msg.id] = msg.analysts || [];
                    $rootScope.$broadcast('nv:presence:updated', { case_id: msg.id, analysts: svc.presence[msg.id] });
                    $rootScope.$apply();
                    break;

                // Phase E8.1 — Visual Vyuha: real-time sighting edge
                // Payload: { type: 'SIGHTING', source_case_id, target_case_id, observable_id, tenant_id, timestamp }
                case 'SIGHTING':
                    $rootScope.$broadcast('nv:graph:sighting', {
                        source_case_id: msg.source_case_id,
                        target_case_id: msg.target_case_id,
                        observable_id: msg.observable_id
                    });
                    break;

                // Phase Z2.1 — Node Manager: live integration node health push
                // Payload: { type: 'NODE_STATUS_CHANGED', node_id, status, latency_ms, timestamp }
                case 'NODE_STATUS_CHANGED':
                    $rootScope.$broadcast('nv:node:statusChanged', {
                        node_id: msg.node_id,
                        status: msg.status,
                        latency_ms: msg.latency_ms,
                        timestamp: msg.timestamp
                    });
                    break;

                case 'CONNECTED':
                    // Server confirmed connection
                    break;

                default:
                    break;
            }
        }

        // ── Start polling fallback ───────────────────────────────────────────
        function _startPolling() {
            if (_pollTimer) return;
            _pollTimer = $interval(function () {
                $rootScope.$broadcast('nv:poll:tick');
            }, POLL_INTERVAL);
        }

        function _stopPolling() {
            if (_pollTimer) {
                $interval.cancel(_pollTimer);
                _pollTimer = null;
            }
        }

        // ── Set online / offline state ───────────────────────────────────────
        function _setOnline() {
            svc.connected = true;
            svc.offline = false;
            _reconnectStep = 0;
            _stopPolling();
            $rootScope.$broadcast('nv:socket:online');
            $rootScope.$apply();
        }

        function _setOffline() {
            svc.connected = false;
            svc.offline = true;
            _startPolling();
            $rootScope.$broadcast('nv:socket:offline');
            $rootScope.$apply();
        }

        // ── Reconnect with backoff ───────────────────────────────────────────
        function _scheduleReconnect() {
            if (_reconnectTimer) return;
            var delay = RECONNECT_STEPS[Math.min(_reconnectStep, RECONNECT_STEPS.length - 1)];
            _reconnectStep++;
            _reconnectTimer = $timeout(function () {
                _reconnectTimer = null;
                svc.connect();
            }, delay);
        }

        // ── Core connect ─────────────────────────────────────────────────────
        svc.connect = function () {
            var token = _getToken();
            var tenantId = _getTenantId();
            if (!token || !tenantId) {
                // Not authenticated yet — try after auth
                return;
            }

            var url = SOCKET_URL + '/' + encodeURIComponent(tenantId) + '?token=' + encodeURIComponent(token);

            try {
                _ws = new WebSocket(url);
            } catch (e) {
                _setOffline();
                _scheduleReconnect();
                return;
            }

            _ws.onopen = function () {
                _setOnline();
                // Re-join current case room if one is open
                if (_currentCaseId) {
                    svc.joinCase(_currentCaseId);
                }
            };

            _ws.onmessage = function (event) {
                try {
                    var msg = JSON.parse(event.data);
                    $rootScope.$apply(function () { _dispatch(msg); });
                } catch (e) {
                    console.warn('NvSocketSrv: unparseable message', event.data);
                }
            };

            _ws.onclose = function () {
                _setOffline();
                _scheduleReconnect();
            };

            _ws.onerror = function () {
                // onclose will follow immediately
            };
        };

        // ── Presence: join / leave ────────────────────────────────────────────
        svc.joinCase = function (caseId) {
            _currentCaseId = caseId;
            if (_ws && _ws.readyState === WebSocket.OPEN) {
                _ws.send(JSON.stringify({ type: 'JOIN_CASE', case_id: caseId }));
            }
        };

        svc.leaveCase = function (caseId) {
            if (caseId === _currentCaseId) {
                _currentCaseId = null;
            }
            if (_ws && _ws.readyState === WebSocket.OPEN) {
                _ws.send(JSON.stringify({ type: 'LEAVE_CASE', case_id: caseId }));
            }
        };

        // ── Disconnect ───────────────────────────────────────────────────────
        svc.disconnect = function () {
            if (_ws) {
                _ws.close();
                _ws = null;
            }
            if (_reconnectTimer) {
                $timeout.cancel(_reconnectTimer);
                _reconnectTimer = null;
            }
            _stopPolling();
        };

        // ── Auto-start when Angular is ready ─────────────────────────────────
        $rootScope.$on('nv:auth:loggedIn', function () {
            svc.connect();
        });

        $rootScope.$on('nv:auth:loggedOut', function () {
            svc.disconnect();
        });

        return svc;
    });
})();
