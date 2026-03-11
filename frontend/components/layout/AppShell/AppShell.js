'use client';

import Sidebar from '../Sidebar/Sidebar';
import Topbar from '../Topbar/Topbar';
import styles from './AppShell.module.css';

export default function AppShell({ children }) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.main}>
        <Topbar />
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}
