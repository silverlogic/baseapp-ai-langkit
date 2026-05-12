import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { EditModalShell } from '../src/EditModalShell';

const NOOP = () => {};

describe('EditModalShell', () => {
  it('renders header and body slots inside the modal chrome', () => {
    render(
      <EditModalShell
        isOpen
        onCancel={NOOP}
        onSave={NOOP}
        header={<div data-testid="hdr">header-content</div>}
        body={<div data-testid="bdy">body-content</div>}
      />,
    );
    expect(screen.getByTestId('rtw-modal')).toBeInTheDocument();
    expect(screen.getByTestId('hdr')).toBeInTheDocument();
    expect(screen.getByTestId('bdy')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-modal-cancel')).toBeInTheDocument();
    expect(screen.getByTestId('rtw-modal-save')).toBeInTheDocument();
  });

  it('Save is disabled when saveDisabled is true', () => {
    render(
      <EditModalShell
        isOpen
        onCancel={NOOP}
        onSave={NOOP}
        saveDisabled
        header={null}
        body={null}
      />,
    );
    expect(screen.getByTestId('rtw-modal-save')).toBeDisabled();
  });

  it('renders nothing when isOpen is false', () => {
    render(
      <EditModalShell
        isOpen={false}
        onCancel={NOOP}
        onSave={NOOP}
        header={null}
        body={null}
      />,
    );
    expect(screen.queryByTestId('rtw-modal')).toBeNull();
  });

  it('calls onCancel when the Cancel button is clicked', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        header={null}
        body={null}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when ESC is pressed', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        header={null}
        body={null}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('asks for confirmation on ESC when dirty', () => {
    const onCancel = vi.fn();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        dirty
        header={null}
        body={null}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled(); // user declined
    confirmSpy.mockRestore();
  });

  it('dismisses on click-outside (backdrop)', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        header={null}
        body={null}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-backdrop'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('does not dismiss on clicks inside the modal', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        header={<button>inside</button>}
        body={null}
      />,
    );
    fireEvent.click(screen.getByText('inside'));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('calls onSave when the Save button is clicked', () => {
    const onSave = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={NOOP}
        onSave={onSave}
        header={null}
        body={null}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-save'));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it('disableOutsideDismiss: ESC is a no-op', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        disableOutsideDismiss
        header={null}
        body={null}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('disableOutsideDismiss: backdrop click is a no-op', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        disableOutsideDismiss
        header={null}
        body={null}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-backdrop'));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('disableOutsideDismiss: Cancel button still works', () => {
    const onCancel = vi.fn();
    render(
      <EditModalShell
        isOpen
        onCancel={onCancel}
        onSave={NOOP}
        disableOutsideDismiss
        header={null}
        body={null}
      />,
    );
    fireEvent.click(screen.getByTestId('rtw-modal-cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows "Saving…" and disables both buttons while saving', () => {
    render(
      <EditModalShell
        isOpen
        onCancel={NOOP}
        onSave={NOOP}
        saving
        header={null}
        body={null}
      />,
    );
    expect(screen.getByTestId('rtw-modal-save')).toHaveTextContent(/saving/i);
    expect(screen.getByTestId('rtw-modal-save')).toBeDisabled();
    expect(screen.getByTestId('rtw-modal-cancel')).toBeDisabled();
  });
});
