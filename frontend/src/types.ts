export type DevelopmentUser = {
  id: string;
  name: string;
  companyName: string;
};

/** Public metadata returned by the API; storage keys are deliberately absent. */
export type UploadRecord = {
  upload_id: string;
  sample_id: string;
  filename: string;
  classification: string;
  status: string;
  created_at: string;
};

export type UploadInitiationMetadata = {
  sample_id: string;
  filename: string;
  classification: string;
  content_type: string;
};

export type UploadInitiation = {
  upload_id: string;
  upload_url: string;
  upload_url_expires_in_seconds: number;
};

export type UploadConfirmation = {
  upload_id: string;
  status: string;
};
