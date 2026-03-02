/**
 * nvAdminCtrl.js — NeuralVyuha Admin Panel
 * Tabs: Platform | Users | System Health
 */
(function () {
    'use strict';

    angular.module('theHiveControllers').controller('NvAdminCtrl', function (
        $scope, $http, $timeout, AuthenticationSrv, NotificationSrv
    ) {
        var vm = this;

        // ── State ──────────────────────────────────────────────────────────
        vm.activeTab = 'platform';
        vm.loading = false;
        vm.platform = {};
        vm.users = [];
        vm.health = {};
        vm.currentUser = AuthenticationSrv.currentUser || {};

        // ── Tab Navigation ─────────────────────────────────────────────────
        vm.setTab = function (tab) {
            vm.activeTab = tab;
            if (tab === 'platform') { vm.loadPlatform(); }
            if (tab === 'users') { vm.loadUsers(); }
            if (tab === 'health') { vm.loadHealth(); }
        };

        // ── Platform ───────────────────────────────────────────────────────
        vm.loadPlatform = function () {
            vm.loading = true;
            $http.get('/api/status').then(function (res) {
                vm.platform = res.data || {};
            }).catch(function () {
                vm.platform = { version: 'NeuralVyuha Zenith', error: 'Could not load platform info' };
            }).finally(function () { vm.loading = false; });
        };

        // ── Users ──────────────────────────────────────────────────────────
        vm.loadUsers = function () {
            vm.loading = true;
            // Show the logged-in admin user; in a full implementation this would
            // call GET /api/v1/user/_list or similar
            $http.get('/api/v1/user/current', {
                headers: { Authorization: 'Bearer ' + localStorage.getItem('nv_token') }
            }).then(function (res) {
                var u = res.data || {};
                vm.users = [{
                    login: u.login || 'admin@neuralvyuha.local',
                    name: u.name || 'Administrator',
                    organisation: u.organisation || 'admin',
                    roles: (u.roles || ['SYSTEM_ADMIN']).join(', '),
                    status: 'Active'
                }];
            }).catch(function () {
                vm.users = [];
            }).finally(function () { vm.loading = false; });
        };

        // ── Health ─────────────────────────────────────────────────────────
        vm.loadHealth = function () {
            vm.loading = true;
            vm.health = {};
            $http.get('/api/status').then(function (res) {
                var data = res.data || {};
                var svc = data.services || {};

                // Map backend service keys → human-readable labels
                var labels = {
                    'nv-query': { name: 'nv-query (API Gateway)', detail: 'REST + JWT Auth' },
                    'opensearch': { name: 'OpenSearch (Persistence)', detail: 'Index: nv-events' },
                    'postgres': { name: 'PostgreSQL (Vault)', detail: 'nv_vault DB' },
                    'minio': { name: 'MinIO (Evidence)', detail: 'AES-256 encrypted' },
                    'redis': { name: 'nv-socket (WebSocket)', detail: 'Redis pub/sub' },
                    'redpanda': { name: 'nv-ingest (Event Spine)', detail: 'Redpanda Kafka' }
                };

                var services = Object.keys(labels).map(function (key) {
                    return {
                        name: labels[key].name,
                        detail: labels[key].detail,
                        status: svc[key] || 'UNKNOWN'
                    };
                });

                var conn = data.connectors || {};
                if (conn.cortex) { services.push({ name: 'Cortex', detail: 'Analyzer Engine', status: conn.cortex.status || 'UNKNOWN' }); }
                if (conn.misp) { services.push({ name: 'MISP', detail: 'Threat Intelligence', status: conn.misp.status || 'UNKNOWN' }); }

                vm.health = { version: data.version || 'N/A', services: services, probeTime: new Date() };
            }).catch(function () {
                vm.health = { error: 'Could not reach backend' };
            }).finally(function () { vm.loading = false; });
        };

        vm.statusClass = function (s) {
            if (!s) { return 'status-unknown'; }
            var u = s.toUpperCase();
            if (u === 'UP' || u === 'OK') { return 'status-up'; }
            if (u === 'DEGRADED' || u === 'WARNING') { return 'status-degraded'; }
            if (u === 'DOWN' || u === 'ERROR') { return 'status-down'; }
            return 'status-unknown';
        };

        // ── Lifecycle ──────────────────────────────────────────────────────
        vm.loadPlatform();
    });
})();
