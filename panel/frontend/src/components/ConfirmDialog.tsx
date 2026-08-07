import { type ReactNode } from 'react';

interface ConfirmProps {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ConfirmDialog({
  open, title, message, confirmText = 'Подтвердить',
  cancelText = 'Отмена', danger, onConfirm, onCancel, loading,
}: ConfirmProps) {
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">{title}</div>
        </div>
        <div className="modal-body">
          <div style={{ fontSize: 14, color: 'var(--fg-secondary)', lineHeight: 1.55 }}>
            {message}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel} disabled={loading}>
            {cancelText}
          </button>
          <button
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading && <span className="spinner" style={{ width: 16, height: 16 }} />}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
