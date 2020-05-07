import numpy as np

def nifti_dicom2mat(orient,patientPosition,xyzMM,verbose = False):
    # DICOM values to 4x4 nifti transformation matrix. As per https://github.com/rordenlab/dcm2niix/blob/7ce33ca5fa3bb2dd4e5410bd97bcf515c9e462d9/console/nifti1_io_core.cpp

    Q = np.zeros((3,3))

    # Q.m[0][0] = orient[1]; Q.m[0][1] = orient[2] ; Q.m[0][2] = orient[3] ; // load Q
    # Q.m[1][0] = orient[4]; Q.m[1][1] = orient[5] ; Q.m[1][2] = orient[6];
    Q[:2,:] = orient # Fill first two rows
    
    # normalize rows
    #import pdb; pdb.set_trace()
    normQ = np.linalg.norm(Q, ord=2, axis=1, keepdims=True)
    normQ[normQ==0.0] = 1.0
    Q /= normQ
    if verbose:
        np.set_printoptions(precision=2)
        print(f'Normalised ImageOrientationPatient in Q:\n {Q}')

    # row 3 is the cross product of rows 1 and 2
    Q[2,:] = np.cross(Q[0,:],Q[1,:])
    if verbose:
        print(f'After slice normal calculation. Q:\n {Q}')

    Q = Q.T
    if np.linalg.det(Q)<0.0:
        Q[:,2] = Q[:,2] *-1

    # next scale matrix
    # I think dcm2niix reversees the pixel spacing: https://github.com/rordenlab/dcm2niix/blob/485c387c93bbca3b29b93403dfde211c4bc39af6/console/nii_dicom.cpp#L5403
    xyzMM[1], xyzMM[0] = xyzMM[0], xyzMM[1]
    diagVox = np.diag(xyzMM)
    Q = Q@diagVox
    if verbose:
        print(f'After scaling. Q:\n {Q}')
        
    # Include translations
    Q44 = np.zeros((4,4))
    Q44[:3,:3] = Q
    Q44[:3,3] = patientPosition
    Q44[3,3] = 1.0
    if verbose:
        print(f'Final Q:\n {Q44}')
    return Q44

def nifti_mat44_to_quatern(R):
    #offset outputs are read  out of input matrix
    qx = R[0,3]
    qy = R[1,3]
    qz = R[2,3]

    #load 3x3 matrix into local variables */
    r11 = R[0,0]
    r12 = R[0,1]
    r13 = R[0,2]
    r21 = R[1,0]
    r22 = R[1,1]
    r23 = R[1,2]
    r31 = R[2,0]
    r32 = R[2,1]
    r33 = R[2,2]

    # compute lengths of each column; these determine grid spacings
    xd = np.sqrt( r11*r11 + r21*r21 + r31*r31 )
    yd = np.sqrt( r12*r12 + r22*r22 + r32*r32 )
    zd = np.sqrt( r13*r13 + r23*r23 + r33*r33 )
    
    #if a column length is zero, patch the trouble
    if xd == 0.0:
        r11 = 1.0
        r21 = 0.0
        r31 = 0.0
        xd = 1.0
    if yd == 0.0:
        r22 = 1.0
        r12 = 0.0
        r32 = 0.0
        yd = 1.0        
    if zd == 0.0:
        r33 = 1.0
        r13 = 0.0
        r23 = 0.0
        zd = 1.0

    # assign the output lengths */
    dx = xd
    dy = yd
    dz = zd
    
    #normalize the columns */
    r11 /= xd
    r21 /= xd
    r31 /= xd
    r12 /= yd
    r22 /= yd
    r32 /= yd
    r13 /= zd
    r23 /= zd
    r33 /= zd  

    zd = r11*r22*r33-r11*r32*r23-r21*r12*r33+r21*r32*r13+r31*r12*r23-r31*r22*r13 # should be -1 or 1
    if zd > 0:# proper
        qfac = 1.0
    else: #%improper ==> flip 3rd column
        qfac=-1.0
        r13 *= -1.0
        r23 *= -1.0
        r33 *= -1.0
    
    # now, compute quaternion parameters
    a = r11 + r22 + r33 + 1.0
    if a > 0.5 :# simplest case
        a = 0.5 * np.sqrt(a)
        b = 0.25 * (r32-r23) / a
        c = 0.25 * (r13-r31) / a
        d = 0.25 * (r21-r12) / a
    else: #trickier case
        xd = 1.0 + r11 - (r22+r33) # 4*b*b
        yd = 1.0 + r22 - (r11+r33) # 4*c*c
        zd = 1.0 + r33 - (r11+r22) # 4*d*d
        if xd > 1.0:
            b = 0.5 * np.sqrt(xd)
            c = 0.25* (r12+r21) / b
            d = 0.25* (r13+r31) / b
            a = 0.25* (r32-r23) / b
        elif yd > 1.0:
            c = 0.5 * np.sqrt(yd)
            b = 0.25* (r12+r21) / c
            d = 0.25* (r23+r32) / c
            a = 0.25* (r13-r31) / c
        else:
            d = 0.5 * np.sqrt(zd)
            b = 0.25* (r13+r31) / d
            c = 0.25* (r23+r32) / d
            a = 0.25* (r21-r12) / d
        
        if a < 0.0:
            b=-b
            c=-c
            d=-d        

    qb = b
    qc = c
    qd = d
    return qb,qc,qd,qx,qy,qz,dx,dy,dz,qfac