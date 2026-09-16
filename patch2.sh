sed -i 's/              variant="secondary"/            <Button\n              variant="secondary"/g' frontend/src/app/security/scans/[id]/page.tsx
sed -i 's/              >/>/g' frontend/src/app/security/scans/[id]/page.tsx
sed -i 's/} Re-run/} Re-run\n            <\/Button>/g' frontend/src/app/security/scans/[id]/page.tsx
