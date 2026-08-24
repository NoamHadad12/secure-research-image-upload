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
