import warnings
warnings.filterwarnings("ignore")
import os
import shutil
import sys

from .classes import (Population, GATools, Selection, Mutation, 
                      Crossover, GAInput, InputHelp, Normalization)
from .classes.exception import PopulationSizeError
from .convenience_tools import (time_it, tar_output, 
                                archive_output, kill_macromodel)

def run():
    
    # Running MacroModel optimizations sometimes leaves applications open.
    # This closes them. If this is not done, directories may not be possible
    # to move. 
    kill_macromodel()
                          
    # Get the name of the input file and load its contents into a 
    # ``GAInput`` instance. Info about input file structure is documented in
    # ``GAInput`` docstring.
    ga_input = GAInput(sys.argv[1])
    
    # If an output folder of MMEA exists, archive it. This just moves any
    # ``output`` folder in the cwd to the ``old_output`` folder.
    archive_output()
    # Save the current directory as the `launch_dir`.
    launch_dir = os.getcwd()
        
    # Create a new output directory and move into it. Save its path as the
    # root directory.
    
    # Wait for previous operations to finish before making a new directory.
    mk_complete = False    
    while not mk_complete:
        try:
            os.mkdir('output')
            mk_complete = True
        except:
            continue
    
    # Copy the input script into the output folder - this is useful for
    # keeping track of what input was used to generate the output.
    shutil.copyfile(sys.argv[1], os.path.join('output', 
                                os.path.split(sys.argv[1])[-1]))
        
    os.chdir('output')
    root_dir = os.getcwd()
    os.mkdir('initial')
    os.chdir('initial')
    
    # Use data from the input file to create a ``GATools`` instance for the
    # main population.
    selector = Selection(ga_input.generational_select_func, 
                         ga_input.parent_select_func, 
                         ga_input.mutant_select_func)
    mator = Crossover(ga_input.crossover_func, ga_input.num_crossovers)
    mutator = Mutation(ga_input.mutation_func, ga_input.num_mutations,
                       weights=ga_input.mutation_weights)
    normalizator = (Normalization(ga_input.normalization_func) if 
                    ga_input.normalization_func else None)
    ga_tools = GATools(selector, mator, mutator, normalizator,
                       ga_input.opt_func, ga_input.fitness_func)
    ga_tools.ga_input = ga_input
    
    # Generate and optimize an initial population.
    with time_it():
        pop_init = getattr(Population, ga_input.init_func.name)
        print(('\n\nGenerating initial population.\n'
             '------------------------------\n\n'))
        
        if pop_init.__name__ == 'load':
            pop = pop_init(**ga_input.init_func.params, ga_tools=ga_tools)
            ga_input.pop_size = len(pop)
            
            for mem in pop:
                prist_name = os.path.basename(mem.prist_mol_file)
                heavy_name = os.path.basename(mem.heavy_mol_file)
                
                mem.prist_mol_file = os.path.join(os.getcwd(), prist_name)
                mem.heavy_mol_file = os.path.join(os.getcwd(), heavy_name)
            
            pop.write_population(os.getcwd())
            
        else:
            pop = pop_init(**ga_input.init_func.params, 
                           size=ga_input.pop_size, ga_tools=ga_tools)
    
    with time_it():    
        print(('\n\nOptimizing the population.\n'
              '--------------------------\n\n'))
        pop = Population(pop.ga_tools, *pop.optimize_population())
    
    with time_it():    
        print('\n\nCalculating the fitness of population members.\n'
            '----------------------------------------------\n\n') 
        pop = Population(pop.ga_tools, *pop.calculate_member_fitness())

    if pop.ga_tools.normalization:
        with time_it():
            print(('\n\nNormalizing fitness values.\n'
                       '---------------------------\n\n'))
            pop.normalize_fitness_values()

    for macro_mol in sorted(pop, key=lambda x : x.fitness, reverse=True):
        print(macro_mol.fitness, '-',macro_mol.prist_mol_file)
            
    # Run the GA.
    for x in range(ga_input.num_generations):
        # Save the min, max and mean values of the population.    
        pop.progress_update()
        
        # Check that the population has the correct size.
        if len(pop) != ga_input.pop_size:
            raise PopulationSizeError('Population has the wrong size.')
        
        print(('\n\nGeneration {0} started. Stop at generation {1}. '
                'Population size is {2}.\n'
                '---------------------------------------------------------'
                '--------------\n\n').format(x, ga_input.num_generations-1, 
                                                len(pop)))
        # At the start of each generation go into the root directory and 
        # create a folder to hold the next generation's ``.mol`` files.
        # Change into the newly created directory.
        os.chdir(root_dir)
        os.mkdir(str(x))
        os.chdir(str(x))
        
        with time_it():
            print('\n\nStarting crossovers.\n--------------------\n\n')
            offspring = pop.gen_offspring()
    
        with time_it():
            print('\n\nStarting mutations.\n-------------------\n\n')
            mutants = pop.gen_mutants()
        
        with time_it():
            print(('\n\nAdding offsping and mutants to population.'
                  '\n------------------------------------------\n\n'))
            pop += offspring + mutants
        
        with time_it():
            print(('\n\nRemoving duplicates, if any.\n'
                   '----------------------------\n\n')    )
            pop.remove_duplicates()        
        
        pop.dump(os.path.join(os.getcwd(), 'unselected_pop_dump'))    
        
        with time_it():        
            print(('\n\nOptimizing the population.\n'
                  '--------------------------\n\n'))
            pop = Population(pop.ga_tools, *pop.optimize_population())
    
        with time_it():        
            print('\n\nCalculating the fitness of population members.\n'
                '----------------------------------------------\n\n')    
            pop = Population(pop.ga_tools, 
                             *pop.calculate_member_fitness())

        if pop.ga_tools.normalization:
            with time_it():
                print(('\n\nNormalizing fitness values.\n'
                           '---------------------------\n\n'))
                pop.normalize_fitness_values()
                
        for macro_mol in sorted(pop, 
                                key=lambda x : x.fitness, reverse=True):
            print(macro_mol.fitness, '-', macro_mol.prist_mol_file)
    
        with time_it():        
            print(('\n\nSelecting members of the next generation.\n'
                   '-----------------------------------------\n\n'))
            pop = pop.gen_next_gen(ga_input.pop_size)
            
        # Create a folder within a generational folder for the the ``.mol``
        # files corresponding to molecules selected for the next generation.
        # Place the ``.mol`` files into that folder.
        print(('\n\nPlacing selected memebers in `selected` directory.\n'
               '--------------------------------------------------\n\n'))
        with time_it():
            os.mkdir('selected')
            os.chdir('selected')
            pop.write_population(os.getcwd())
            pop.dump(os.path.join(os.getcwd(), 'pop_dump'))
    
        
    # Running MacroModel optimizations sometimes leaves applications open.
    # This closes them. If this is not done, directories may not be possible
    # to move.     
    kill_macromodel()
    
    # Update a final time and plot the results of the GA run.
    pop.progress_update()
    pop.plot.epp(os.path.join(root_dir, 'epp.png'))
    
    # Move the ``output`` folder into the ``old_output`` folder.
    os.chdir(launch_dir)
    
    with time_it():
        tar_output()
        
    with time_it():
        archive_output()
    
def helper():
    InputHelp(sys.argv[-1])

def compare():
    # If an output folder of MMEA exists, archive it. This just moves any
    # ``output`` folder in the cwd to the ``old_output`` folder.
    archive_output()
        
    # Create a new output directory and move into it. Save its path as the
    # root directory.
    
    # Wait for previous operations to finish before making a new directory.
    mk_complete = False    
    while not mk_complete:
        try:
            os.mkdir('output')
            mk_complete = True
        except:
            continue
    
    # Copy the input script into the output folder - this is useful for
    # keeping track of what input was used to generate the output.
    shutil.copyfile(sys.argv[2], os.path.join('output', 
                                os.path.split(sys.argv[2])[-1]))
        
    # Create the encapsulating population.
    pop = Population()
    # Get the fitness and normazliation function data from the input 
    # file.
    inp = GAInput(sys.argv[2])
    
    # Give the population a GATools instance.
    pop.ga_tools = Population.load(sys.argv[3]).ga_tools
    # Load the fitness and normalization functions into it.
    pop.ga_tools.fitness = inp.fitness_func
    pop.ga_tools.normalization = (Normalization(inp.normalization_func) if 
                    inp.normalization_func else None)    
    
    pops = [Population.load(pop_path) for pop_path in sys.argv[3:]]
   
    launch_dir = os.getcwd()
    os.chdir('output')      
   
    # For each population re-calculate the fitness values using the 
    # fitness function specified in the input file.
    for i, sp in enumerate(pops):
        for ind in sp:
            ind.unscaled_fitness = None
            ind.fitness_fail = None
            ind.fitness = None

        for ind_i, ind in enumerate(sp):
            ind.prist_mol_file = '{}.mol'.format(ind_i)
        sp.write_population('cpop{}'.format(i))
        
        sp = Population(*sp.calculate_member_fitness(), sp.ga_tools)
        pop.add_subpopulation(sp)
    
    if inp.normalization_func:
        pop.normalize_fitness_values()    
    
    pop.plot.subpopulations('fitness_comparison.png')
    pop.plot.progress_params('param_comparison.png')
    
    os.chdir(launch_dir)
    archive_output()
    
if __name__ == '__main__':
    if '-h' in sys.argv:
        helper()
    elif '-c' in sys.argv:
        compare()
    else:
        run()


