# PTMC-Rostering

## TO ADD
- RHMC daytime rostering 
- RHMC leave schedule
- RHMC AMPT status
- RHMC personnel ORD dates
- Ability to generate/regenerate  PTMC or RHMC only(?)
    - For consideration due to factors such as compassionate leave, sudden MA.   
    - Regenarate on a daily/weekly basis instead(?)                   
- Lower priority for plotted duties for personnel with pending AMPT pass (?)
- MUST be with respect to AMPT test date
    - i.e if AMPT is on 22/07, personnel can be planned up to 20/07 with lower(?) duty/cover priority
    - AMPT fail but plotted for duty after AMPT date
- No weekday duties for personnel going on course
    - Weekends during their course are still susceptible to duties (LOCAL only)
- Native availability forecast editor in webapp(?)
    - Only blank templates would be required for planning each month(?)
    - Eliminates need for having to upload a file everytime a roster needs to be generated
- Cover eligibility
    - CBT has higher priority for covers, SLIGHTLY lower priority for duties
    - SVC has higher priority for duties, low priority for covers
        - MUST be deemed cover fit before being rostered for SHORT covers
        - Interest can be indicated for longer covers, subject to approval & manpower constraints

## TO DO
- Confirmation of rulebook and assumptions
    - Hard and soft constraints
- Optimal team comps
- Cover planning

## CURRENT STATE
- DOES NOT plan covers(PTRH) and RHMC day duties
- Able to allocate manpower appropriately for mon, thurs, sun
- Able to produce mock roster
- Role prioritisation not the most optimal
    - Senior getting assigned junior role while junior gets slightly less junior role
        - CFC GERALD(P061) getting AE whilst LCP JARED JUAY(P065) getting SB1
- Ensures that each day prioritises having 1 person per department in a single duty where possible
    - i.e there should be no instance of 2x admin on the same duty
- Validates availability befote planning
    - This works hypothetically, NOT verified in practice










