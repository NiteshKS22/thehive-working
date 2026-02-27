/**
 * nvVisualVyuhaCtrl.js — Phase E8.1: Visual Vyuha Attack Graph Controller
 *
 * Responsibilities:
 *  - Fetch graph data from GET /graph/case/{id} via NvApiSrv
 *  - Initialise Cytoscape.js canvas with colour-coded node styling
 *  - Apply cose-bilkent (or cose fallback) auto-layout
 *  - Handle node click → open Quick-Triage panel
 *  - Filter timeline to show only events related to the selected node  
 *  - Listen for nv:graph:sighting WS events → animate new edge in real-time
 *
 * Guardrails:
 *  TENANT_PRIVACY  - cross-tenant nodes rendered as "Seen in another tenant" (server-enforced)
 *  PERFORMANCE     - canvas renderer, max 500 nodes server-side
 *  INTERACTIVITY   - clicking any node opens Quick-Triage panel
 */
(function () {
    'use strict';

    angular.module('theHive').controller('NvVisualVyuhaCtrl', function (
        $scope, $routeParams, $timeout, NvApiSrv, NvSocketSrv, NotificationSrv
    ) {

        var vm = this;
        var cy = null;                // Cytoscape instance

        // ── State ─────────────────────────────────────────────────────────────
        vm.caseIdInput = $routeParams.caseId || '';
        vm.loading = false;
        vm.graphLoaded = false;
        vm.truncated = false;
        vm.nodeCount = 0;
        vm.edgeCount = 0;
        vm.selected = null;      // selected node data
        vm.selectedDetail = null;  // case detail from API
        vm.selectedTimeline = [];
        vm.selectedNeighbours = [];
        vm.selectedNeighbourCount = 0;
        vm.triageLoading = false;
        vm.liveConnected = NvSocketSrv.connected;

        // ── Node colour map ───────────────────────────────────────────────────
        //   Red=case, Blue=ip/domain, Green=file/hash, Yellow=user, Purple=cross_tenant
        var NODE_COLORS = {
            'case': { bg: '#e05c6a', border: '#c04455', text: '#fff' },
            'ip': { bg: '#4a9eff', border: '#2a7de0', text: '#fff' },
            'domain': { bg: '#4a9eff', border: '#2a7de0', text: '#fff' },
            'hash': { bg: '#3ecf8e', border: '#28a870', text: '#fff' },
            'file': { bg: '#3ecf8e', border: '#28a870', text: '#fff' },
            'user': { bg: '#f5c842', border: '#d4a820', text: '#1a1a1a' },
            'cross_tenant': { bg: '#9b77e8', border: '#7a5dcc', text: '#fff' }
        };

        var DEFAULT_COLOR = { bg: '#718096', border: '#4a5568', text: '#fff' };

        // ── Cytoscape stylesheet ──────────────────────────────────────────────
        function _buildStylesheet() {
            var styles = [
                {
                    selector: 'node',
                    style: {
                        'label': 'data(label)',
                        'font-size': '11px',
                        'font-family': 'Inter, Roboto, sans-serif',
                        'color': '#e2e8f0',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'text-wrap': 'ellipsis',
                        'text-max-width': '80px',
                        'width': '40px',
                        'height': '40px',
                        'border-width': '2px',
                        'border-opacity': 0.9,
                        'transition-property': 'background-color, border-color, width, height',
                        'transition-duration': '0.15s',
                        'transition-timing-function': 'ease'
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'width': '52px',
                        'height': '52px',
                        'border-width': '3px',
                        'border-color': '#fff',
                        'z-index': 100
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#2d3448',
                        'target-arrow-color': '#2d3448',
                        'target-arrow-shape': 'triangle',
                        'arrow-scale': 0.8,
                        'curve-style': 'bezier',
                        'opacity': 0.7
                    }
                },
                {
                    selector: 'edge[label = "shares_observable"]',
                    style: {
                        'line-color': '#4a9eff',
                        'target-arrow-color': '#4a9eff',
                        'width': 2.5
                    }
                },
                // New sighting edge (animated flash)
                {
                    selector: '.new-sighting',
                    style: {
                        'line-color': '#f5c842',
                        'target-arrow-color': '#f5c842',
                        'width': 3,
                        'opacity': 1
                    }
                }
            ];

            // Per-type node colour selectors
            Object.keys(NODE_COLORS).forEach(function (nodeType) {
                var c = NODE_COLORS[nodeType];
                styles.push({
                    selector: 'node[node_type = "' + nodeType + '"]',
                    style: {
                        'background-color': c.bg,
                        'border-color': c.border,
                        'color': c.text
                    }
                });
            });

            // Case nodes slightly larger
            styles.push({
                selector: 'node[node_type = "case"]',
                style: { 'width': '50px', 'height': '50px', 'font-weight': '700' }
            });

            return styles;
        }

        // ── Initialise / destroy Cytoscape ────────────────────────────────────
        function _initCy(elements) {
            if (cy) {
                cy.destroy();
                cy = null;
            }

            cy = cytoscape({
                container: document.getElementById('nv-graph-container'),
                elements: elements,
                style: _buildStylesheet(),
                // Initial (fast) layout – replaced by cose-bilkent below
                layout: { name: 'grid' },
                // Performance settings
                textureOnViewport: true,
                motionBlur: false,
                pixelRatio: 'auto',
                hideEdgesOnViewport: true // hide edges while panning for performance
            });

            // Node click → open Quick-Triage
            cy.on('tap', 'node', function (evt) {
                $scope.$apply(function () {
                    _openTriage(evt.target.data());
                });
            });

            // Background tap → close triage
            cy.on('tap', function (evt) {
                if (evt.target === cy) {
                    $scope.$apply(function () { vm.closePanel(); });
                }
            });

            // Run the proper layout after init
            _runLayout();
        }

        // ── Layout ────────────────────────────────────────────────────────────
        function _runLayout() {
            if (!cy) return;
            var layoutName = (typeof cytoscapeCoseBilkent !== 'undefined') ? 'cose-bilkent' : 'cose';
            var layout = cy.layout({
                name: layoutName,
                nodeRepulsion: 4500,
                idealEdgeLength: 100,
                edgeElasticity: 0.45,
                gravity: 0.25,
                numIter: 2500,
                animate: true,
                animationDuration: 800,
                fit: true,
                padding: 40,
                randomize: false
            });
            layout.run();
        }

        vm.runLayout = _runLayout;

        vm.fitAll = function () {
            if (cy) { cy.fit(undefined, 40); }
        };

        // ── Load graph ────────────────────────────────────────────────────────
        vm.loadGraph = function () {
            var caseId = (vm.caseIdInput || '').trim();
            if (!caseId) return;

            vm.loading = true;
            vm.graphLoaded = false;
            vm.selected = null;
            vm.truncated = false;
            vm.nodeCount = 0;
            vm.edgeCount = 0;

            NvApiSrv.getCaseGraph(caseId).then(function (data) {
                if (!data || !data.nodes) {
                    NotificationSrv.log('Visual Vyuha', 'Graph returned no data.', 'warning');
                    return;
                }

                vm.truncated = data.truncated;
                vm.nodeCount = data.node_count;
                vm.edgeCount = data.edge_count;

                // Build Cytoscape elements array
                var elements = [];

                data.nodes.forEach(function (n) {
                    elements.push({
                        group: 'nodes',
                        data: {
                            id: n.id,
                            label: _truncateLabel(n.label || n.id, 24),
                            node_type: n.node_type,
                            tenant_id: n.tenant_id,
                            severity: n.severity,
                            status: n.status
                        }
                    });
                });

                data.edges.forEach(function (e, i) {
                    elements.push({
                        group: 'edges',
                        data: {
                            id: 'edge-' + i,
                            source: e.source,
                            target: e.target,
                            label: e.label,
                            observable: e.observable
                        }
                    });
                });

                $timeout(function () {
                    _initCy(elements);
                    vm.graphLoaded = true;
                    vm.loading = false;

                    // If a case node is the seed, auto-open its triage
                    if (data.seed_case_id) {
                        var seedNode = _findNodeData(data.seed_case_id);
                        if (seedNode) {
                            $timeout(function () { _openTriage(seedNode); }, 900);
                        }
                    }
                }, 50);

            }).catch(function (err) {
                vm.loading = false;
                if (err && err.status === 404) {
                    NotificationSrv.log('Visual Vyuha', 'Case not found: ' + caseId, 'error');
                } else {
                    NotificationSrv.log('Visual Vyuha', 'Failed to load graph.', 'error');
                }
            });
        };

        // ── Quick-Triage Panel ────────────────────────────────────────────────
        function _findNodeData(nodeId) {
            if (!cy) return null;
            var n = cy.getElementById(nodeId);
            return n && n.length ? n.data() : null;
        }

        function _openTriage(nodeData) {
            vm.selected = nodeData;
            vm.selectedDetail = null;
            vm.selectedTimeline = [];
            vm.selectedNeighbours = [];
            vm.selectedNeighbourCount = 0;

            // Highlight selected node
            if (cy) {
                cy.nodes().removeClass('selected-node');
                cy.getElementById(nodeData.id).addClass('selected-node');
            }

            if (nodeData.node_type === 'case') {
                _loadCaseTriage(nodeData.id);
            } else if (nodeData.node_type !== 'cross_tenant') {
                _loadObservableTriage(nodeData.id);
            }
        }

        function _loadCaseTriage(caseId) {
            vm.triageLoading = true;

            // Fetch case detail + timeline in parallel
            NvApiSrv.getCase(caseId).then(function (data) {
                vm.selectedDetail = data;
            }).catch(angular.noop);

            NvApiSrv.getCaseTimeline(caseId).then(function (data) {
                vm.selectedTimeline = data && data.timeline ? data.timeline : [];
            }).catch(angular.noop).finally(function () {
                vm.triageLoading = false;
            });
        }

        function _loadObservableTriage(nodeId) {
            if (!cy) return;
            // Find all case-neighbours connected to this observable node
            var neighbours = cy.getElementById(nodeId).neighborhood('node[node_type = "case"]');
            var result = [];
            neighbours.each(function (n) {
                result.push({ id: n.data('id'), label: n.data('label'), node_type: n.data('node_type') });
            });
            vm.selectedNeighbours = result;
            vm.selectedNeighbourCount = result.length;
        }

        vm.closePanel = function () {
            vm.selected = null;
            if (cy) { cy.nodes().removeClass('selected-node'); }
        };

        vm.selectNodeById = function (nodeId) {
            var nodeData = _findNodeData(nodeId);
            if (nodeData) {
                _openTriage(nodeData);
                // Pan to node
                if (cy) {
                    cy.animate({
                        center: { eles: cy.getElementById(nodeId) },
                        zoom: Math.max(cy.zoom(), 1.2)
                    }, { duration: 400 });
                }
            }
        };

        // ── Real-Time: SIGHTING event from Vyuha-Stream ───────────────────────
        //
        // When a new SIGHTING event arrives over the WebSocket the nvSocketSrv
        // broadcasts 'nv:graph:sighting' with { source_case_id, target_case_id, observable_id }.
        // We add the new edge (and nodes if needed) and flash it yellow briefly.
        //
        $scope.$on('nv:graph:sighting', function (evt, payload) {
            if (!cy || !vm.graphLoaded) return;

            var srcId = payload.source_case_id;
            var tgtId = payload.target_case_id;
            var obsId = payload.observable_id;

            // Ensure source node exists
            if (cy.getElementById(srcId).length === 0) {
                cy.add({
                    group: 'nodes', data: {
                        id: srcId, label: srcId, node_type: 'case', tenant_id: ''
                    }
                });
            }
            // Ensure target node exists
            if (cy.getElementById(tgtId).length === 0) {
                cy.add({
                    group: 'nodes', data: {
                        id: tgtId, label: tgtId, node_type: 'case', tenant_id: ''
                    }
                });
            }

            var edgeId = 'sighting-' + srcId + '-' + tgtId + '-' + Date.now();
            var newEdge = cy.add({
                group: 'edges', data: {
                    id: edgeId,
                    source: srcId,
                    target: tgtId,
                    label: 'sighting',
                    observable: obsId
                }
            });

            // Flash animation: add class, remove after 2.5s
            newEdge.addClass('new-sighting');
            $timeout(function () {
                if (newEdge && !newEdge.removed()) {
                    newEdge.removeClass('new-sighting');
                }
            }, 2500);

            $scope.$apply(function () {
                vm.edgeCount = cy.edges().length;
                vm.nodeCount = cy.nodes().length;
            });

            // Notify analyst
            NotificationSrv.log(
                '⚡ New Sighting',
                'Observable <strong>' + obsId + '</strong> links a new case.',
                'info'
            );
        });

        // ── Live-indicator: track socket status ───────────────────────────────
        $scope.$on('nv:socket:online', function () { $scope.$apply(function () { vm.liveConnected = true; }); });
        $scope.$on('nv:socket:offline', function () { $scope.$apply(function () { vm.liveConnected = false; }); });

        // ── Helper: truncate long labels ─────────────────────────────────────
        function _truncateLabel(str, max) {
            if (!str) return '';
            return str.length > max ? str.slice(0, max) + '…' : str;
        }

        // ── Auto-load if caseId in route params ───────────────────────────────
        if (vm.caseIdInput) {
            vm.loadGraph();
        }

        // ── Cleanup ───────────────────────────────────────────────────────────
        $scope.$on('$destroy', function () {
            if (cy) { cy.destroy(); cy = null; }
        });

    });
})();
