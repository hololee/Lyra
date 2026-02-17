import { type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Modal from './Modal';
import { hasStoredUserName } from '../utils/userIdentity';

interface UserNameGuardProps {
  children: ReactNode;
}

export default function UserNameGuard({ children }: UserNameGuardProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  if (hasStoredUserName()) {
    return <>{children}</>;
  }

  const moveToSettings = () => {
    navigate('/settings');
  };

  return (
    <Modal
      isOpen={true}
      onClose={moveToSettings}
      onConfirm={moveToSettings}
      title={t('auth.userNameRequiredTitle')}
      message={t('auth.userNameRequiredMessage')}
      type="confirm"
    />
  );
}
