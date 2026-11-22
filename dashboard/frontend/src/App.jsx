import React, { useState, useEffect } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import Overview from './pages/Overview';
import Investigations from './pages/Investigations';
import RiskClusters from './pages/RiskClusters';
import Transactions from './pages/Transactions';
import ModelIntelligence from './pages/ModelIntelligence';
import SystemArchitecture from './pages/SystemArchitecture';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught rendering error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 bg-[#C64B43]/10 border border-[#C64B43]/25 rounded-xl font-mono text-xs text-[#C64B43] space-y-3">
          <div className="flex items-center gap-2 text-[#C64B43] font-bold text-sm">
            <span>Operational Interface Error</span>
          </div>
          <p className="text-[#3D4543]">
            An error occurred while rendering this view: {this.state.error?.message || 'Unknown error'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              if (this.props.onReset) this.props.onReset();
            }}
            className="px-3 py-1.5 bg-[#C64B43]/15 hover:bg-[#C64B43]/25 text-[#C64B43] rounded border border-[#C64B43]/30 text-xs font-semibold"
          >
            Reload Module
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const getInitialParam = (param, fallback) => {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get(param);
      if (p) return p;
    }
    return fallback;
  };

  const [currentPage, setCurrentPage] = useState(getInitialParam('page', 'overview'));
  const [selectedAccountId, setSelectedAccountId] = useState(getInitialParam('account', null));
  const [selectedClusterId, setSelectedClusterId] = useState(getInitialParam('cluster', null));

  // Sync state to URL and handle browser history
  const navigateTo = (page, overrides = {}) => {
    setCurrentPage(page);
    let nextAccount = selectedAccountId;
    let nextCluster = selectedClusterId;

    if ('account' in overrides) {
      nextAccount = overrides.account;
      setSelectedAccountId(nextAccount);
    }
    if ('cluster' in overrides) {
      nextCluster = overrides.cluster;
      setSelectedClusterId(nextCluster);
    }

    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('page', page);
      if (nextAccount && page === 'investigations') {
        url.searchParams.set('account', nextAccount);
      } else {
        url.searchParams.delete('account');
      }
      if (nextCluster && page === 'clusters') {
        url.searchParams.set('cluster', nextCluster);
      } else {
        url.searchParams.delete('cluster');
      }
      window.history.pushState(null, '', url.toString());
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const page = params.get('page') || 'overview';
      const acc = params.get('account') || null;
      const clu = params.get('cluster') || null;
      setCurrentPage(page);
      setSelectedAccountId(acc);
      setSelectedClusterId(clu);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleSearchAccount = (accountId) => {
    navigateTo('investigations', { account: accountId });
  };

  const handleSelectAccount = (accountId) => {
    setSelectedAccountId(accountId);
    navigateTo('investigations', { account: accountId });
  };

  const handleSelectCluster = (clusterId) => {
    setSelectedClusterId(clusterId);
    navigateTo('clusters', { cluster: clusterId });
  };

  return (
    <div className="min-h-screen bg-[#F3F1EB] text-[#252B29] flex font-sans">
      {/* Fixed Left Sidebar */}
      <Sidebar currentPage={currentPage} onNavigate={(p) => navigateTo(p)} />

      {/* Main Content Area */}
      <div className="flex-1 ml-64 flex flex-col min-h-screen">
        {/* Fixed Top Bar */}
        <TopBar
          currentPage={currentPage}
          selectedAccountId={selectedAccountId}
          selectedClusterId={selectedClusterId}
          onNavigate={(p) => navigateTo(p)}
          onSearchAccount={handleSearchAccount}
          highRiskCount={436}
        />

        {/* Page Content View */}
        <main className="flex-1 mt-14 px-8 py-6 max-w-7xl w-full mx-auto">
          <ErrorBoundary onReset={() => setCurrentPage('overview')}>
            {currentPage === 'overview' && (
              <Overview
                onNavigate={(p) => navigateTo(p)}
                onSelectAccount={handleSelectAccount}
                onSelectCluster={handleSelectCluster}
              />
            )}

            {currentPage === 'investigations' && (
              <Investigations
                selectedAccountId={selectedAccountId}
                onSelectAccount={handleSelectAccount}
                onNavigate={(p) => navigateTo(p)}
              />
            )}

            {currentPage === 'clusters' && (
              <RiskClusters
                selectedClusterId={selectedClusterId}
                onSelectCluster={handleSelectCluster}
                onSelectAccount={handleSelectAccount}
                onNavigate={(p) => navigateTo(p)}
              />
            )}

            {currentPage === 'transactions' && (
              <Transactions
                onSelectAccount={handleSelectAccount}
                onNavigate={(p) => navigateTo(p)}
              />
            )}

            {currentPage === 'models' && <ModelIntelligence />}

            {currentPage === 'system' && <SystemArchitecture />}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
