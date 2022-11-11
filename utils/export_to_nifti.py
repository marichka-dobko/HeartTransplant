import os
import numpy as np
import pydicom as dicom
import glob
import nibabel as nib


def get_first_scan(path_patient):
    all_scans = glob.glob(path_patient + '/**')
    years = [int(i.split('/')[-1].split('-')[2]) for i in all_scans]
    first_year = np.sort(years)[0]
    scan = [el for el in all_scans if '-' + str(first_year) + '-' in el][0]
    return scan


def load_sample(exam_path):
    slices_exam = glob.glob(exam_path + '/**')
    d = {sl_exam: int(sl_exam.split('/')[-1].split('-')[-1][:-4]) for sl_exam in slices_exam}
    sorted_dict = {k: v for k, v in sorted(d.items(), key=lambda item: item[1])}
    slices = [dicom.dcmread(sl).pixel_array for sl in sorted_dict.keys()]
    return np.stack(slices, -1)


if __name__ == '__main__':
    input_dir = '/Users/mariadobko/Documents/Cornell/LAB/NLST First 60 Raw'
    save_dir = '/Users/mariadobko/Documents/Cornell/LAB/NLST_nifti'

    patients_cases = glob.glob(input_dir + '/**/**')
    failed_patients = []
    t = {}
    for case in patients_cases:
        # Create directory for a patient
        case_id = case.split('/')[-1]
        t.update({case_id: []})

        path_to_save = save_dir + '/' + case_id

        scan_path = get_first_scan(case)
        scans = glob.glob(scan_path + '/**')

        # Check number of dicoms
        scans = [s for s in scans if len(glob.glob(s + '/**')) > 10]
        sc = [len(glob.glob(scan + '/**')) for scan in scans]
        maxvalues_index = np.argwhere(sc == np.amax(sc)).flatten().tolist()
        scans = [scans[i] for i in maxvalues_index]

        if len(scans) != 1:
            # Pick the correct Hounsfield units
            filtered_scans = []

            for scan in scans:
                slice_test = glob.glob(scan + '/**')[0]
                dc = dicom.dcmread(slice_test)
                t[case_id].append((dc.WindowWidth, dc.WindowCenter))

                try:
                    if int(dc.WindowWidth[0]) == 400 or int(dc.WindowWidth[0]) == 350:
                        filtered_scans.append(scan)
                except:
                    if int(dc.WindowWidth) == 400 or int(dc.WindowWidth) == 350:
                        filtered_scans.append(scan)

            # If both scans have the same width, center, then save the one with more slices
            if t[case_id][0] == t[case_id][1]:
                sc = [len(glob.glob(scan + '/**')) for scan in scans]
                filtered_scans.append(scans[np.argmax(sc)])
            scans = filtered_scans

        if len(scans) == 0:
            failed_patients.append(case_id)
        else:
            chosen_scan = scans[0]

            # Open the scans and save to NIFTI
            array = np.array(load_sample(chosen_scan), dtype=np.float32)

            affine = np.eye(4)
            nifti_file = nib.Nifti1Image(array, affine)

            scan_path_save = path_to_save + '.nii'
            nib.save(nifti_file, scan_path_save)

    # for c in failed_patients:
    #     print(c, t[c])
    print(len(failed_patients))
