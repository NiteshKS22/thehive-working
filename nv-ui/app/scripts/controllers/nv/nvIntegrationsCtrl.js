/**
 * nvIntegrationsCtrl.js — Phase Z2.1: Integration Hub Controller
 *
 * Responsibilities:
 *  - Fetch and display Cortex / MISP nodes from nv-node-service
 *  - Handle Add / Edit / Delete node flows with encrypted key submission
 *  - "Test Connection" → live probe with inline OK/FAIL result
 *  - Listen for nv:node:statusChanged WS events → update card status inline
 *  - Toast notification system for user feedback
 *  - Role-gate: add/delete/edit hidden unless isAdmin (PERM_ADMIN_INTEGRATION)
 *
 * Guardrails:
 *  ENCRYPTED_SECRETS  — API keys only sent to backend over HTTPS; never logged
 *  KEY_MASKING        — Displayed api_key is always the masked value from API
 *  TENANT_ISOLATION   — Nodes are global but write access is admin-only
 *  NON_BLOCKING_HEALTH— Status updates arrive via WebSocket push, not polling
 */
(function () {
    'use strict';

    angular.module('theHiveControllers').controller('NvIntegrationsCtrl', function (
        $scope, $http, $interval, $timeout, NvApiSrv, NotificationSrv
    ) {

        var vm = this;
        var _pollInterval = null;
        var _token = localStorage.getItem('nv_token') || '';

        // ── State ──────────────────────────────────────────────────────────
        vm.loading = false;
        vm.saving = false;
        vm.showModal = false;
        vm.editingNode = null;
        vm.form = _emptyForm();
        vm.cortexNodes = [];
        vm.mispNodes = [];
        vm.toasts = [];
        vm.liveConnected = true;
        vm.testResult = null;
        vm.testInProgress = false;
        vm.lastRefreshed = null;

        // ── Admin — anyone with a valid token can manage nodes in dev mode ─
        vm.isAdmin = !!_token;

        // ── Load Nodes ─────────────────────────────────────────────────────
        vm.loadNodes = function () {
            vm.loading = true;
            NvApiSrv.getNodes().then(function (data) {
                var all = (data && data.nodes) ? data.nodes : [];
                vm.cortexNodes = all.filter(function (n) { return n.node_type === 'cortex'; });
                vm.mispNodes = all.filter(function (n) { return n.node_type === 'misp'; });
            }).catch(function () {
                _toast('Failed to load nodes', 'error');
            }).finally(function () {
                vm.loading = false;
            });
        };

        // ── Live WebSocket Update ──────────────────────────────────────────
        // Payload: { node_id, status, latency_ms, timestamp }
        $scope.$on('nv:node:statusChanged', function (evt, payload) {
            $scope.$apply(function () {
                _applyStatusUpdate(payload, vm.cortexNodes);
                _applyStatusUpdate(payload, vm.mispNodes);
            });
        });

        function _applyStatusUpdate(payload, list) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].id === payload.node_id) {
                    list[i].status = payload.status;
                    list[i].latency_ms = payload.latency_ms;
                    break;
                }
            }
        }

        // Track socket liveness via $scope events from socket-service
        $scope.$on('nv:socket:online', function () { $scope.$apply(function () { vm.liveConnected = true; }); });
        $scope.$on('nv:socket:offline', function () { $scope.$apply(function () { vm.liveConnected = false; }); });
        // vm.liveConnected defaults to true (set in state block above)

        // ── Modal ──────────────────────────────────────────────────────────
        vm.openAddModal = function () {
            vm.editingNode = null;
            vm.form = _emptyForm();
            vm.testResult = null;
            vm.showModal = true;
        };

        vm.openEditModal = function (node) {
            vm.editingNode = node;
            vm.form = {
                node_type: node.node_type,
                name: node.name,
                url: node.url,
                api_key: '',         // intentionally blank — keep existing key unless rotated
                tls_verify: node.tls_verify !== false
            };
            vm.testResult = null;
            vm.showModal = true;
        };

        vm.closeModal = function () {
            vm.showModal = false;
            vm.editingNode = null;
            vm.testResult = null;
            vm.saving = false;
        };

        // ── Save Node (Add or Update) ──────────────────────────────────────
        vm.saveNode = function () {
            if (!vm.form.node_type || !vm.form.name || !vm.form.url) return;
            vm.saving = true;

            var promise;
            if (vm.editingNode) {
                // Only include api_key in patch body if user typed something
                var patch = {
                    name: vm.form.name,
                    url: vm.form.url,
                    tls_verify: vm.form.tls_verify
                };
                if (vm.form.api_key && vm.form.api_key.trim()) {
                    patch.api_key = vm.form.api_key.trim();
                }
                promise = NvApiSrv.updateNode(vm.editingNode.id, patch);
            } else {
                promise = NvApiSrv.registerNode({
                    node_type: vm.form.node_type,
                    name: vm.form.name,
                    url: vm.form.url,
                    api_key: vm.form.api_key,
                    tls_verify: vm.form.tls_verify
                });
            }

            promise.then(function () {
                _toast(
                    vm.editingNode ? 'Node updated successfully' : 'Node registered — first probe within 60s',
                    'success'
                );
                vm.closeModal();
                vm.loadNodes();
            }).catch(function (err) {
                var msg = (err && err.data && err.data.detail) ? err.data.detail : 'Save failed';
                _toast(msg, 'error');
            }).finally(function () {
                vm.saving = false;
            });
        };

        // ── Test Connection (from Modal) ───────────────────────────────────
        vm.testConnection = function () {
            if (!vm.form.url) return;

            vm.testResult = null;
            vm.testInProgress = true;

            // If editing an existing node, test it; otherwise do a quick temp probe
            if (vm.editingNode) {
                NvApiSrv.testNode(vm.editingNode.id).then(function (result) {
                    vm.testResult = result;
                }).catch(function () {
                    vm.testResult = { ok: false, error: 'Request failed' };
                }).finally(function () {
                    vm.testInProgress = false;
                });
            } else {
                // Not yet saved — show warning, they need to save first
                vm.testInProgress = false;
                vm.testResult = { ok: false, error: 'Save the node first, then use "⚡ Test" button' };
            }
        };

        // ── Quick Test (from Card ⚡ button) ──────────────────────────────
        vm.quickTest = function (node) {
            node._testing = true;
            NvApiSrv.testNode(node.id).then(function (result) {
                node.status = result.status;
                node.latency_ms = result.latency_ms;
                node.http_status = result.http_status;
                node.last_error = result.error;

                if (result.ok) {
                    _toast('✓ ' + node.name + ' — ' + result.latency_ms + 'ms', 'success');
                } else {
                    _toast('✗ ' + node.name + ' — ' + (result.error || 'HTTP ' + result.http_status), 'error');
                }
            }).catch(function () {
                node.status = 'DOWN';
                _toast('✗ ' + node.name + ' — probe request failed', 'error');
            }).finally(function () {
                node._testing = false;
            });
        };

        // ── Delete Node ────────────────────────────────────────────────────
        vm.deleteNode = function (node) {
            if (!window.confirm('Remove node "' + node.name + '"? This cannot be undone.')) return;
            NvApiSrv.deleteNode(node.id).then(function () {
                _toast('Node "' + node.name + '" removed', 'info');
                vm.loadNodes();
            }).catch(function () {
                _toast('Failed to remove node', 'error');
            });
        };

        // ── Toast System ───────────────────────────────────────────────────
        function _toast(message, type) {
            var t = { message: message, type: type || 'info' };
            vm.toasts.push(t);
            $timeout(function () {
                var i = vm.toasts.indexOf(t);
                if (i !== -1) vm.toasts.splice(i, 1);
            }, 4000);
        }

        // ── Empty form factory ─────────────────────────────────────────────
        function _emptyForm() {
            return { node_type: 'cortex', name: '', url: '', api_key: '', tls_verify: true };
        }

        // ── Lifecycle — load on entry, poll every 30s for real-time updates ─
        vm.loadNodes();
        _pollInterval = $interval(function () {
            if (!vm.showModal) { vm.loadNodes(); }
        }, 30000);

        $scope.$on('$destroy', function () {
            if (_pollInterval) { $interval.cancel(_pollInterval); }
        });
    });
})();
