import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles/theme.css';
import './styles/components.css';
import './styles/layout.css';

const basename = (() => {
  const p = window.location.pathname;
  const m = p.match(/^(\/[^/]+)\/(login|$)/);
  return m ? m[1] : '';
})();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
