#= Development-only reflection of the published public Core payload closure.

No solve, Core private access, persistence codec or dependency installation. Output is a
descriptor plus constructor-only manufactured declarations, not a validated exact restart.
Run with the workspace's already prepared Julia project and depot. --check never writes.
=#
using QCLNEGF, Unitful, SHA

const ROOT_NAMES = (:ExactExecutionIdentity, :ExactRestartIdentity, :ExactSolverState,
    :ScientificHistorySnapshot, :SolverEvent, :CompletedStateEvidence, :CoreDatum)
const BASE = normpath(joinpath(@__DIR__, ".."))
const CORE_ROOT = normpath(joinpath(BASE,"..","QCLNEGF.jl"))
realpath(pathof(QCLNEGF)) == realpath(joinpath(CORE_ROOT,"src","QCLNEGF.jl")) ||
    error("Loaded Core source differs from the selected workspace checkout")
isempty(strip(read(`git --no-optional-locks -C $CORE_ROOT status --porcelain`,String))) ||
    error("Publish the owning Core source before exporting its public contract")
const NODES = Dict{String,Any}()
const TYPES = Dict{String,Any}()
const VALIDATED = Set{Tuple{String,Bool}}()
const VISITING = Set{Tuple{String,Bool}}()

function json(value)
    value === nothing && return "null"
    value isa Bool && return value ? "true" : "false"
    value isa Integer && return string(value)
    if value isa AbstractString
        io = IOBuffer(); write(io, '"')
        for char in value
            char == '"' ? write(io, "\\\"") : char == '\\' ? write(io, "\\\\") :
                char == '\n' ? write(io, "\\n") : char == '\r' ? write(io, "\\r") :
                char == '\t' ? write(io, "\\t") :
                Int(char) < 32 ? write(io, "\\u", string(Int(char); base=16, pad=4)) : write(io, char)
        end
        write(io, '"'); return String(take!(io))
    end
    value isa AbstractDict && return "{" * join((json(string(k))*":"*json(value[k])
        for k in sort!(collect(keys(value)); by=string)), ",") * "}"
    value isa Union{Tuple,AbstractVector} && return "["*join(json.(collect(value)), ",")*"]"
    error("Unsupported reflection JSON value: $(typeof(value))")
end

function typeid(T)
    T === Any && return "Any"
    T === CoreDatum && return "CoreDatum"
    T isa Union && return "Union_" * bytes2hex(sha256(string(T)))[1:16]
    T isa UnionAll && error("Unresolved public type $T")
    raw = string(T)
    T <: CoreArray && return "CoreArray{"*string(eltype(fieldtype(T,2)))*"}"
    isempty(T.parameters) && return string(nameof(T))
    return "Type_" * bytes2hex(sha256(raw))[1:16]
end

numeric_storage(T) = T in (Bool,Int8,Int16,Int32,Int64,UInt8,UInt16,UInt32,UInt64,
                           Float32,Float64,ComplexF32,ComplexF64)

function visit(T, path="root"; allow_any=false)
    # Qualification belongs to this occurrence, before any type/container cache lookup.
    T === Any && !allow_any && error("Unqualified Any at $path")
    id = typeid(T)
    context = (id,allow_any)
    (context in VALIDATED || context in VISITING) && return id
    push!(VISITING,context)
    try
        haskey(NODES,id) || (NODES[id] = Dict("kind"=>"pending"))
        TYPES[id] = T
        node = if T === Any
            # The only permitted Any island is SCBAResult.restart_contract's Dict values.
            Dict("kind"=>"dynamic", "scope"=>"SCBAResult.restart_contract")
        elseif T === CoreDatum
            bound = Base.unwrap_unionall(CoreArray).parameters[1].ub
            variants = Any[CoreScalar,CoreList,CoreRecord]
            append!(variants, (CoreArray{U} for U in Base.uniontypes(bound)))
            Dict("kind"=>"union", "variants"=>[visit(U,path) for U in variants])
        elseif T isa Union
            Dict("kind"=>"union", "variants"=>[visit(U,path;allow_any) for U in Base.uniontypes(T)])
        elseif T === Nothing
            Dict("kind"=>"nothing")
        elseif T === Bool
            Dict("kind"=>"bool")
        elseif T === String
            Dict("kind"=>"string")
        elseif T === Symbol
            Dict("kind"=>"symbol")
        elseif T <: Integer
            Dict("kind"=>"integer", "type"=>string(T), "bits"=>8sizeof(T), "signed"=>T <: Signed)
        elseif T in (Float32,Float64)
            Dict("kind"=>"ieee", "type"=>T === Float64 ? "f64" : "f32", "digits"=>2sizeof(T))
        elseif T <: Complex
            Dict("kind"=>"complex", "component"=>visit(T.parameters[1],path))
        elseif T <: Unitful.AbstractQuantity
            Dict("kind"=>"quantity", "unit"=>string(unit(zero(T))), "value"=>visit(T.parameters[1],path))
        elseif T <: AbstractArray
            E = eltype(T)
            Dict("kind"=>"array", "eltype"=>string(E), "rank"=>ndims(T),
                 "element"=>visit(E,path*"[]"), "storage"=>numeric_storage(E) ? "dataset" : "items")
        elseif T <: Tuple
            params = collect(T.parameters)
            if length(params)==1 && Base.isvarargtype(params[1])
                V=params[1]; element=visit(V.T,path*"[]")
                isdefined(V,:N) ? Dict("kind"=>"tuple", "elements"=>fill(element,V.N)) :
                    Dict("kind"=>"tuple", "element"=>element)
            else
                Dict("kind"=>"tuple", "elements"=>[visit(U,path*"[]") for U in params])
            end
        elseif T <: AbstractDict
            K,V=T.parameters
            K in (String,Symbol) || error("Unsupported dictionary key at $path: $K")
            Dict("kind"=>"dict", "key"=>visit(K,path*".key"),
                 "value"=>visit(V,path*".value";allow_any))
        elseif isstructtype(T) && (parentmodule(T) === parentmodule(ExactSolverState) || T <: Pair ||
                                   parentmodule(T) === parentmodule(PhysicalParameters))
            Dict("kind"=>"struct", "julia_type"=>string(T), "fields"=>[
                Dict("name"=>string(name), "type"=>visit(kind,path*"."*string(name);
                    allow_any=(T === SCBAResult && name === :restart_contract)))
                for (name,kind) in zip(fieldnames(T),fieldtypes(T))])
        else
            error("Unqualified public type at $path: $T")
        end
        NODES[id]=node
        push!(VALIDATED,context)
        return id
    finally
        delete!(VISITING,context)
    end
end

intwire(x) = Dict("kind"=>"integer","type"=>string(typeof(x)),"decimal"=>string(x))
function wire(value)
    T=typeof(value)
    value===nothing && return nothing
    value isa Bool && return value
    value isa String && return value
    value isa Symbol && return Dict("kind"=>"symbol","value"=>string(value))
    value isa Integer && return intwire(value)
    value isa Float64 && return Dict("kind"=>"ieee","type"=>"f64",
        "bits"=>string(reinterpret(UInt64,value);base=16,pad=16))
    value isa Float32 && return Dict("kind"=>"ieee","type"=>"f32",
        "bits"=>string(reinterpret(UInt32,value);base=16,pad=8))
    value isa Complex && return Dict("kind"=>"complex","real"=>wire(real(value)),"imag"=>wire(imag(value)))
    value isa Unitful.AbstractQuantity && return Dict("kind"=>"quantity","unit"=>string(unit(value)),"value"=>wire(ustrip(value)))
    value isa Tuple && return wire.(collect(value))
    if value isa AbstractArray
        node=Dict{String,Any}("kind"=>"array", "eltype"=>string(eltype(value)),
            "shape"=>string.(collect(size(value))), "order"=>"F")
        if numeric_storage(eltype(value))
            node["file"]=Dict("path"=>"manufactured.h5","bytes"=>"0","sha256"=>repeat("0",64),
                "media_type"=>"application/x-hdf5","schema"=>"qcl-negf-checkpoint-v5")
            node["dataset"]="/manufactured/"*string(eltype(value))*"/"*join(size(value),"x")
        else
            node["values"]=wire.(vec(value))
        end
        return node
    end
    if value isa AbstractDict
        return Dict("kind"=>"dict","entries"=>[
            Dict("key"=>wire(k),"value"=>wire(value[k])) for k in sort!(collect(keys(value));by=string)])
    end
    id=typeid(T); haskey(NODES,id) || visit(T,"fixture")
    return Dict("type"=>id,"fields"=>Dict(string(n)=>wire(getfield(value,n)) for n in fieldnames(T)))
end

function producer_fixture()
    scalars=[name===:r_Jchange ? reinterpret(Float64,0x7ff8000000000001) : 0.0
             for (name,T) in zip(fieldnames(SCBAIteration),fieldtypes(SCBAIteration)) if T===Float64]
    row=SCBAIteration(1, scalars..., nothing,nothing)
    outer=OuterIteration(1, ntuple(_->0.0,9)..., [0.25,0.75], [1.0,2.0])
    snapshot=ScientificHistorySnapshot(;stage=:scba,domain_revision=0,discretization_id="grid",
        basis_id="basis",outer_iteration=1,inner_iteration=1,sequence=7,converged=false,
        status=:running,quality=:unresolved,strict_streak=0,diagnostic_streak=0,row)
    values=Any[snapshot, SolverEvent(:sample,:scba,"manufactured",:running,1,2,
        (SolverMetric(:r,NaN,"1"),),"",8,1,1)]
    append!(values, [CoreScalar(Symbol("")),CoreScalar(Symbol("x")),CoreScalar("")])
    context=AcceptanceContext(;backend=:not_executed,algorithms=AlgorithmOptions(),
        hilbert_roundoff_measured=nothing,map_kernels_shared_with_solver=nothing,
        final_state_alignment=:producer_aligned)
    report=ConvergenceReport(false,Dict{Symbol,Float64}(:r_D=>NaN),["manufactured, no measurement"])
    original=FinalEvidenceSnapshot(;report,original_converged=false,original_status=:nonfinite,
        observations=CoreRecord(Dict("missing"=>nothing,"signed_zero"=>-0.0,"failed"=>Inf)))
    completed=CompletedStateEvidence(;original,
        revalidation=RevalidationReceipt(;status=:error,reason=:not_executed,detail="manufactured",context,report),
        independent_oracle=IndependentOracleReceipt(;status=:not_measured,reason=:not_requested,
            detail="",context=nothing,report=nothing))
    push!(values,completed)
    push!(values,ExactExecutionIdentity(;core_code="manufactured-code",julia=string(VERSION),
        blas="manufactured-blas",fftw="manufactured-fftw",scalar_type="Float64/ComplexF64",
        index_type=string(Int),reduction="static_chunks_v1",worker_count=1,blas_threads=1,
        energy_chunk=1,hilbert_columns=1,residual_chunk=1,parallel_backend=:threads))
    green=GreenState(ntuple(_->zeros(ComplexF64,3,2,1,1),4)...,zeros(3,2),ones(3,2))
    family()=SelfEnergyFamily(ntuple(_->zeros(ComplexF64,3,2,1,1),3)...)
    scba=SCBAResult(green,Dict{Symbol,SelfEnergyFamily}(),family(),family(),family(),[row],
        false,:running,:unresolved,nothing,SCBAMixerState())
    identity=ExactRestartIdentity(UInt16(1),ntuple(_->UInt8(0),32),ntuple(_->UInt8(1),32),ntuple(_->UInt8(2),32))
    state=ExactSolverState(;identity,boundary=:outer_accepted,published_U=[0.0,1.0],published_n=[1.0,2.0],
        scba,mixer_position=MixerPosition(;applied_mixes=0,retained_mix_indices=(),last_reset_mix=0,
            last_reset_reason=:none,last_coefficient_fallback=:none),family_order=(:embedding_plus,:embedding_minus),
        outer_history=[outer],progress=SolverProgress(1,1,1,0,0,0),
        continuation=OuterContinuation(;next_U=[0.0,1.0],next_action=:next_outer),status=:running,
        warnings=(),policy_evaluations=(),adaptation=nothing,measurement_context=context,final_evidence=nothing)
    push!(values,state)
    bits=[0x0000000000000000,0x8000000000000000,0x7ff0000000000000,
          0xfff0000000000000,0x7ff8000000000001,0x7ff8000000000002]
    return Dict("scope"=>"constructors_only_not_validated_restart","values"=>wire.(values),
        "array_declarations_only"=>true,"ieee_bits"=>[wire(reinterpret(Float64,b))["bits"] for b in bits])
end

check = "--check" in ARGS
roots=[visit(getproperty(QCLNEGF,name),string(name)) for name in ROOT_NAMES]
fixture=producer_fixture()
graph=Dict("roots"=>roots,"nodes"=>NODES)
revision=strip(read(`git --no-optional-locks -C $CORE_ROOT rev-parse HEAD`,String))
layout=Dict("format"=>"qcl-negf.core-layout.v1","graph"=>graph,
    "layout_sha256"=>bytes2hex(sha256(json(graph))),
    "producer"=>Dict("core_revision"=>revision,"julia"=>string(VERSION),"scope"=>"public_types_only"))
for (path,value) in ((joinpath(BASE,"src/qcl_negf_contracts/core_layout.json"),layout),
                    (joinpath(BASE,"tests/fixtures/results-v2/core-producer.json"),fixture))
    payload=json(value)*"\n"
    if check
        isfile(path) && read(path,String)==payload || error("Generated Core resource differs: $path")
    else
        mkpath(dirname(path)); write(path,payload)
    end
end
println("Public Core reflection: ",length(NODES)," types; constructors only; layout ",layout["layout_sha256"],
    check ? "; check passed" : "; generated")
