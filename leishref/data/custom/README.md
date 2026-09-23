the 4  entries:
- Ltropica.Ld1S.scaffold.flye/           
- Ltropica.Ld1S.scaffold.pecat/
- Ltropica.Ld1S.scaffold.flye.filtered/  
- Ltropica.Ld1S.scaffold.pecat.filtered/

The scaffolds were made as follows. First, assemblies were made with LORA v1.0.0 using flye/pecat and filtering/no filtering of reads below 1000bp. LORA produces the contigs. 

Then, we built scaffold on Ld1S genome where accession were replaced by chromosome number 1, 2, 3, .., 36. maxicircle using::

     leishref renamed-sequences --flavor number Ld1S.fasta
     ragtag scaffold Ld1S.number.fa Ltropica.fasta

We edit the ragtag fasta file to prune _RagTag suffix. 

We sort contigs (by number) and renamed extra contigs as extr_contig_1, 2, ... using sort_fasta.py from leishref.

Then, we add in a stage (to publish)::

    leishref dev add NAME.fasta
    leishref dev publish to_publish/NAME.fasta


