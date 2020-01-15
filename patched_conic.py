#!/usr/bin/env python3

"""References:

* Arthur Gagg Filho, L., & da Silva Fernandes, S. 2016. Optimal round
  trip lunar missions based on the patched-conic approximation.
  Computational and Applied Mathematics, 35(3),
  753–787. https://doi.org/10.1007/s40314-015-0247-y

"""

import numpy as np

from orbit import Orbit

def rotate_2d(theta):
    return np.array([[np.cos(theta), -np.sin(theta)],
                     [np.sin(theta),  np.cos(theta)]])

class PatchedConic(Orbit):
    # Physical constants of earth--moon system
    D = 384402000.0 # distance from earth to moon in m
    OMEGA = 2.649e-3 # r/s
    V = OMEGA * D # mean velocity of moon relative to earth in m/s
    
    R = 1737000.0 # m -- radius of moon
    mu = 4.9048695e12 # m^3/s^2 moon gravitational constant
    mu_earth = 3.986004418e14 # m^3/s^2 earth gravitational constant
    r_soi = (mu / mu_earth)**0.4 * D
    
    def __init__(self, depart, arrive,
                 lam1    = 0.0,
                 rf      = 1837000.0):
        """Construct a planar patched conic approximation of an earth--moon
        transfer.

        Args:
          depart  earth-centered orbit at time of departure (post delta-v;
                  delta-v is assumed to be relative to a circular orbit of
                  the same radius)
          arrive  earth-centered orbit at SOI intercept
          lam1    spacecraft phase angle at arrival (angle between vector to
                  sphere-of-influence intercept and moon--earth
                  vector)
          rf      final desired radius of lunar orbit

        """

        self.depart  = depart
        self.arrive  = arrive
        self.lam1    = lam1
        self.rf      = rf

        # E: eccentric anomaly in the transit orbit; E0 is departure,
        #    E1 is SOI intercept
        cE0  = depart.cos_E
        cE1  = arrive.cos_E
        E0   = np.arccos(cE0)
        E1   = np.arccos(cE1)
        sE0  = np.sin(E0)
        sE1  = np.sin(E1)

        e    = arrive.e

        # Get duration from departure from earth (time 0) to SOI
        # intercept (time 1)
        if arrive.a <= 0:
            raise ValueError("expected elliptical trajectory")
        tof  = np.sqrt(arrive.a**3 / arrive.mu) * ((E1 - e * sE1) - (E0 - e * sE0))


        # Get true anomalies at departure and arrival; we'll need
        # these to get departure phase angle.
        cnu0 = depart.cos_nu
        cnu1 = arrive.cos_nu
        nu0  = np.arccos(cnu0)
        nu1  = np.arccos(cnu1)

        # Get phase angle at arrival
        sg1 = np.clip((self.r_soi / arrive.r) * np.sin(lam1), -1.0, 1.0)
        gam1 = np.arcsin(sg1) # gam1 is opposite lam1 in the arrival
                              # triangle (see Fig 1); phase angle at
                              # arrival
        
        # gam0 is the phase angle at departure
        gam0 = nu1 - nu0 - gam1 - self.OMEGA * tof

        # Eq. 9: velocity relative to moon when we reach SOI
        v1 = arrive.v
        v2 = np.sqrt(v1**2 + self.V**2 - 2.0 * v1 * self.V * np.cos(arrive.phi - gam1))

        # Angle of selenocentric velocity relative to moon's center
        phi1 = arrive.phi

        # Compute miss angle of hyperbolic trajectory
        seps2 = np.clip( (self.V * np.cos(lam1) - v1 * np.cos(lam1 + gam1 - phi1)) / -v2, -1.0, 1.0 )
        eps2  = np.arcsin(seps2)

        # Eq. 10: Get selenocentric flight path angle 
        # right-hand side:
        tan_lam1_pm_phi2 = - v1 * np.sin(phi1 - gam1) / (self.V - v1 * np.cos(phi1 - gam1))
        phi2 = np.arctan(tan_lam1_pm_phi2) - lam1 # flight path angle

        # Parameters for Orbit class
        self.r   = self.r_soi
        self.v   = v2
        self.phi = phi2
        self.eps = eps2

        # Additional parameters
        self.Q   = self.r * self.v**2 / self.mu
        self.rf  = rf
        self.vf  = np.sqrt(self.mu / self.rf)
        self.gam0 = gam0
        self.E0   = E0
        self.nu0  = nu0
        self.t0   = 0.0
        self.gam1 = gam1
        self.E1   = E1
        self.nu1  = nu1
        self.t1   = tof

        # Calculate eccentricity and semimajor axis using Eqs 52--53.
        Q2 = self.Q
        self.ef   = np.sqrt(1.0 + Q2 * (Q2 - 2.0) * np.cos(phi2)**2)
        self.af   = self.r / (2.0 - Q2)

        # Position and velocity at perilune
        self.rpl  = self.af * (1.0 - self.ef)
        self.vpl  = np.sqrt((self.mu * (1.0 + self.ef)) / (self.af * (1.0 - self.ef)))

        # Compute gradients for SGRA
        self.compute_gradients()

        
    def compute_gradients(self):
        orbit = self
        
        # Setup some shorthand notations
        v0 = orbit.depart.v
        v1 = orbit.arrive.v
        v2 = orbit.v
        vM = orbit.V
        
        Q2 = orbit.Q

        phi0 = orbit.depart.phi
        phi1 = orbit.arrive.phi
        gam1 = orbit.gam1

        phi2 = orbit.phi
        cphi2 = np.cos(phi2)
        sphi2 = np.sin(phi2)

        cphi1 = np.cos(phi1)
        sphi1 = np.sin(phi1)
        tphi1 = np.tan(phi1)
        cgam1 = np.cos(gam1)
        cpmg1 = np.cos(phi1 - gam1)
        spmg1 = np.sin(phi1 - gam1)

        ef = self.ef
        af = self.af

        lam1  = orbit.lam1

         # Eq. 57--61
        self.dv1_dv0     = v0 / v1
        self.dphi1_dv0   = (v0 / v1 - v1 / v0) / (v1 * tphi1)
        self.dv2_dv0     = ((v1 - vM * cpmg1) / v2) * self.dv1_dv0 + ((v1 * vM * spmg1) / v2) * self.dphi1_dv0
        self.dphi2_dv1   = -vM * spmg1 / v2**2
        self.dphi2_dphi1 = (v1**2 - v1 * vM * cpmg1) / v2**2
        self.dphi2_dv0   = self.dphi2_dv1 * self.dv1_dv0 + self.dphi2_dphi1 * self.dphi1_dv0

        # Eq. 63--65
        self.def_dv2     = 2 * Q2 * (Q2 - 1.0) * cphi2**2 / (ef * v2)
        self.def_dphi2   = -Q2 * (Q2 - 2.0) * cphi2 * sphi2 / ef
        self.def_dv0     = self.def_dv2 * self.dv2_dv0 + self.def_dphi2 * self.dphi2_dv0
        self.daf_dv0     = (2 * af**2 * v2 * self.dv2_dv0) / self.mu
        self.drpl_daf    = 1.0 - ef # rpl = r_perilune
        self.drpl_def    = af
        self.drpl_dv0    = self.drpl_daf * self.daf_dv0 - self.drpl_def * self.def_dv0

        # Optimization state for Newton's method / restoration
        self.x = np.array([lam1, v0])

        # Additional shorthand variables needed for SGRA optimization
        mu      = orbit.depart.mu
        mu_moon = orbit.mu
        r0    = orbit.depart.r
        r1    = orbit.arrive.r
        r2    = orbit.r
        D     = orbit.D
        slam1 = np.sin(lam1)
        clam1 = np.cos(lam1)
        h     = orbit.arrive.h
        
        self.deltav1 = np.abs(v0 - np.sqrt(mu / r0))
        self.deltav2 = orbit.vpl - orbit.vf

        self.dv1_dlam1 = -mu * D * r2 * slam1 / (v1 * r1**3)    # Eq. 66
        self.dphi1_dlam1   = h * D * r2 * slam1 / (v1 * r1**3 * sphi1) - h * D * r2 * mu * slam1 / (v1**3 * r1**4 * sphi1) # Eq. 67
        self.dgam1_dlam1 = r2 * clam1 / (r1 * cgam1) - D * (r2 * slam1)**2 / (r1**3 * cgam1) # Eq. 68

        self.dv2_dlam1 = ((v1 - vM * cpmg1) * self.dv1_dlam1
                          + (v1 * vM * spmg1) * self.dphi1_dlam1
                          - (v1 * vM * spmg1) * self.dgam1_dlam1) / v2 # Eq. 69
        self.dphi2_dgam1 = (vM * v1 * cpmg1 - v1**2) / v2**2 # Eq. 71

        # Eq. 73: Note --- this is only one portion of this equation;
        # we aren't using the rest right now.
        self.dphi2_dlam1 = self.dphi2_dphi1 * self.dphi1_dlam1 + self.dphi2_dgam1 * self.dgam1_dlam1 + self.dphi2_dv1 * self.dv1_dlam1 - 1.0

        self.dQ2_dlam1 = 2 * r2 * v2 * self.dv2_dlam1 / mu_moon # Eq. 74
        self.daf_dQ2   = af / (2.0 - Q2) # Eq. 75
        self.def_dQ2   = (Q2 - 1.0) * cphi2**2 / ef # Eq. 76

        self.daf_dlam1 = self.daf_dQ2 * self.dQ2_dlam1 # Eq. 78
        self.def_dlam1 = self.def_dQ2 * self.dQ2_dlam1 + self.def_dphi2 * self.dphi2_dlam1 # Eq. 79
        self.drpl_dlam1 = (1.0 - ef) * self.daf_dlam1 - af * self.def_dlam1 # Eq. 80
        self.dg_drpl    = -1.0
        self.dg_dlam1   = self.dg_drpl * self.drpl_dlam1
        self.dg_dv0     = -self.drpl_dv0 # Eq. 88, but equation in paper should be negated
        self.ddeltav2_dvpl = 1.0
        self.dvpl_daf      = 0.5 * np.sqrt((mu_moon * (1.0 + ef)) / (af**3 * (1.0 - ef))) # Eq. 89 (negated)
        self.dvpl_def      = -np.sqrt(mu_moon / ((1.0 + ef) * af * (1.0 - ef)**3)) # Eq. 90 (negated)
        self.ddeltav2_def  = self.ddeltav2_dvpl * self.dvpl_def
        self.ddeltav2_daf  = self.ddeltav2_dvpl * self.dvpl_daf
        self.dvpl_dlam1     = self.dvpl_daf * self.daf_dlam1 + self.dvpl_def * self.def_dlam1
        self.ddeltav2_dlam1 = self.ddeltav2_dvpl * self.dvpl_dlam1
        self.df_dlam1 = self.ddeltav2_dlam1
        self.ddeltav1_dv0   = 1.0
        self.dvpl_dv0       = self.dvpl_def * self.def_dv0 + self.dvpl_daf * self.daf_dv0
        self.ddeltav2_dv0   = self.ddeltav2_dvpl * self.dvpl_dv0
        self.df_dv0         = self.ddeltav1_dv0 + self.ddeltav2_dv0
        self.f              = self.deltav1 + self.deltav2
        self.df_dx          = np.array([[self.df_dlam1, self.df_dv0]]).T
        self.dg_dx          = np.array([[self.dg_dlam1, self.dg_dv0]]).T
        self.g              = orbit.rf - self.rpl

        # SGRA computations
        dgdx = self.dg_dx # phi_x
        dfdx = self.df_dx # f_x
        P = 1.0 / dgdx.T.dot(dgdx)
        self.lam = -P.dot(dgdx.T.dot(dfdx))[0,0]
        self.P = self.g**2

        self.dF_dx = dfdx + dgdx.dot(self.lam)
        self.F     = self.f + self.g * self.lam

        Fx = self.dF_dx
        self.Q_opt = Fx.T.dot(Fx)[0,0]

    def plot(self, alpha = 1.0, ax = None, v_scale = 100.0):

        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle
        from scipy.linalg import norm

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

            # Plot moon, earth
            moon = Circle( (x.D, 0.0), 1737400.0, fc='grey', ec='grey', alpha=0.5)
            earth = Circle( (0.0, 0.0), 6371000.0, fc='blue', ec='blue', alpha=0.5)
            ax.add_patch(moon)
            ax.add_patch(earth)
            
            # Plot orbit of moon
            moon_orbit = Circle( (0.0, 0.0), self.D, fill=False, fc=None, alpha=0.5)
            ax.add_patch(moon_orbit)

            # Plot lunar SOI
            soi = Circle( (self.D, 0.0), self.r_soi, fill=False, fc=None, alpha=0.5)
            ax.add_patch(soi)

        # Plot from earth to intercept point, intercept point to moon
        # Find intercept point, call it r1
        r1 = rotate_2d(self.gam1).dot(np.array([self.arrive.r, 0.0]))
        ax.plot([0.0, r1[0], self.D],
                [0.0, r1[1], 0.0], c='k', alpha=alpha)

        # Plot moon-relative velocity
        r2_moon = rotate_2d(-self.lam1).dot(np.array([-self.r_soi, 0.0]))
        r2_earth = r2_moon + np.array([x.D, 0.0])
        v2_earth = rotate_2d(self.eps).dot(r2_moon / norm(r2_moon)) * -self.v * v_scale
        ax.plot([r2_earth[0], r2_earth[0] + v2_earth[0]],
                [r2_earth[1], r2_earth[1] + v2_earth[1]], c='r', alpha=alpha)

        # Plot earth-relative velocity
        v1 = rotate_2d(np.pi/2 - self.arrive.phi).dot(r1 / norm(r1)) * self.arrive.v * v_scale
        ax.plot([r1[0], r1[0] + v1[0]], [r1[1], r1[1] + v1[1]], c='g', alpha=alpha)

        vm = np.array([0.0, -self.V]) * v_scale
        ax.plot([r1[0] + v1[0], r1[0] + v1[0] + vm[0]], [r1[1] + v1[1], r1[1] + v1[1] + vm[1]], c='b', alpha=alpha)
        
        return ax

            


    #def dF_dx(self, lam):
    #    """Augmented function F derivative (for SGRA)"""
    #    return self.df_dx + self.dg_dx.dot(lam)

    #def F(self, lam):
    #    """Augmented function for SCGRA."""
    #    return self.f + self.g * lam

    #def Q(self, lam):
    #    """Stopping condition for SCGRA"""
    #    Fx = self.dF_dx(lam)
    #    return Fx.T.dot(Fx)[0,0]

def init_patched_conic(solution_x, dx = np.array([[0.0], [0.0]])):
    """Take some PatchedConic object and vary it in its optimization
    parameters by a vector dx, returning a new PatchedConic.

    """
    if type(solution_x) == PatchedConic:
        solution_x = (solution_x.depart.r, solution_x.depart.v, solution_x.depart.phi, solution_x.lam1, solution_x.rf)
    
    D         = PatchedConic.D
    r_soi     = PatchedConic.r_soi
    r0        = solution_x[0]
    v0        = solution_x[1] + dx[1,0]
    phi0      = solution_x[2]
    lam1      = solution_x[3] + dx[0,0]
    rf        = solution_x[4]
    r1        = np.sqrt(D**2 + r_soi**2 - 2.0 * D * r_soi * np.cos(lam1))
    depart    = Orbit(PatchedConic.mu_earth, r0, v0, phi0)
    intercept = depart.at(r1, sign='+')
    if np.isnan(intercept.v):
        import pdb
        pdb.set_trace()
        raise ValueError("expected radius is not reached")
    
    return PatchedConic(depart, intercept, lam1 = lam1, rf = rf)

    
def Psi(alpha, solution_x, p):
    solution_y = init_patched_conic(solution_x, -p * alpha)
    return solution_y.f + solution_y.g * solution_x.lam


class SGRA(object):
    D = PatchedConic.D
    V = PatchedConic.V
    OMEGA = PatchedConic.OMEGA
    mu_moon = PatchedConic.mu
    mu_earth = PatchedConic.mu_earth
    r_soi = PatchedConic.r_soi
    
    def __init__(self,
                 gtol           = 5e-8,
                 ftol           = 1e-15,
                 Qtol           = 2e-15,
                 alphatol       = 1e-6,
                 beta           = 1.0):
        self.gtol           = gtol
        self.ftol           = ftol
        self.Qtol           = Qtol
        self.alphatol       = alphatol
        self.beta0          = beta

    def optimize_v0(self, solution_x,
                    max_iterations = 100,
                    verbose        = False):
        """Find a departure velocity which allows us to fulfill our perilune
        constraint to within gtol.

        Args:
            max_iterations   maximum number of iterations
            verbose          print Newton's method output each iteration

        Yields:
            The PatchedConic object with all of the relevant
        optimization information during each iteration.

        """
        beta = self.beta0
        
        for ii in range(0, max_iterations):

            # Stop if we reach our desired constraint tolerance
            if np.abs(solution_x.g) <= self.gtol:
                break

            dv0 = -beta * (solution_x.g / solution_x.dg_dv0)

            # If update fails, try again with a smaller beta. If it
            # passes, reset beta to the initial, and keep on going.
            try:
                solution_xt = init_patched_conic(solution_x, np.array([[0.0], [dv0]]))

                # If the result is better, keep it; otherwise discard and split beta
                if np.abs(solution_xt.g) < np.abs(solution_x.g):
                    solution_x = solution_xt
                    retry = False
                else:
                    retry = True
                
            except ValueError:
                retry = True

            if retry:
                beta *= 0.5
            else:
                if verbose:
                    print("v0:         {}".format(solution_x.depart.v))
                    print("constraint: {}".format(solution_x.g))
                    print("gradient:   {}".format(solution_x.dg_dv0))
                    print("beta:       {}".format(beta))
                    print("dv0:        {}".format(dv0))
                    print("eps:        {}".format(solution_x.eps * 180/np.pi))
                    print("------------------------------")
                
                yield solution_x

                beta = self.beta0


    def optimize_deltav(self, solution_x,
                        max_restore_iterations  = 100,
                        max_optimize_iterations = 100,
                        verbose                 = False):

        # Flags
        underflow = False

        # Start by optimizing until we meet our constraint.
        self.optimize_v0(x, max_iterations = max_restore_iterations, verbose = verbose)
        x = np.array([[self.lam1], [self.v0]]) # SGRA state
        solution_xt = solution_x
        xt = np.array(x)
        current_f = solution_x.f

        p   = solution_x.dF_dx
        if self.conjugate:
            Fx2 = solution_x.Q_opt

        for jj in range(0, max_optimize_iterations):
            if underflow:
                raise ValueError("unable to optimize due to restoration underflow")
            elif self.Q_opt <= self.Qtol:
                break

            alpha = minimize_scalar(Psi, method = 'golden', bracket = [1e-14, 3e-5],
                                    args=(self,p), tol=self.alphatol).x
            for ii in range(0, max_restore_iterations):
                dx = -alpha * p
                y  =  xt + dx
                if np.all(y == xt):
                    underflow = True
                    break

                solution_y = init_patched_conic(solution_xt, dx)

                if self.conjugate:
                    Fhatx2 = np.array(Fx2)
                    phat   = np.array(p)

                solution_xt = restore_patched_conic(solution_y,
                                                    tol            = self.gtol,
                                                    max_iterations = max_restore_iterations,
                                                    verbose        = verbose)

                if self.conjugate:
                    Fx2 = solution_xt.Q_opt
                    gamma = Fx2 / Fhatx2
                
                p   = solution_xt.dF_dx + gamma * phat

                # If original solution is better than the current one, try a smaller step
                if solution_xt.f < self.f:
                    break
                else:
                    alpha *= 0.9
                    if alpha <= 1e-15:
                        raise ValueError("unable to optimize due to step underflow")

            if ii + 1 == max_iterations:
                raise ValueError("exceeded max iterations during restoration")
        
        
        # Looks like we found a result. Let's update the object.
        self.lam1 = solution_xt.lam1
        self.r1   = np.sqrt(self.D**2 + self.r_soi**2 - 2.0 * self.D * self.r_soi * np.cos(solution_xt.lam1))
        self.update(solution_xt.v0)



if __name__ == '__main__':

    import matplotlib.pyplot as plt

    ax = None

    leo    = Orbit.circular(PatchedConic.mu_earth, 6371400.0 + 185000.0) # earth parking
    x      = init_patched_conic((leo.r, leo.v + 3225.0, 0.0, np.pi/2.0, 1937000.0))
    opt    = SGRA()
    alpha  = 1.0
    for x in opt.optimize_v0(x, verbose=True):
        ax = x.plot(alpha = alpha, ax = ax)
        alpha *= 0.5
        
        #import pdb
        #pdb.set_trace()
        pass

    plt.show()

    import pdb
    pdb.set_trace()
